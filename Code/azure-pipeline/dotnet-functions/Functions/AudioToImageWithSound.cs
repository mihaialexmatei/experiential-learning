using System.ClientModel;
using System.Text;
using System.Text.Json;
using System.Text.Json.Serialization;
using Azure.AI.OpenAI;
using Azure.Storage.Blobs;
using Microsoft.Azure.Functions.Worker;
using Microsoft.Azure.Functions.Worker.Http;
using Microsoft.CognitiveServices.Speech;
using Microsoft.CognitiveServices.Speech.Audio;
using Microsoft.Extensions.Logging;
using OpenAI.Chat;
using dotnet_functions.Services;

namespace dotnet_functions.Functions;

/// <summary>
/// End-to-end HTTP trigger function that returns BOTH image and sound for Unity integration:
/// 1. Receives an audio file
/// 2. Converts speech to text using Azure Speech Service
/// 3. Enhances the text using Azure OpenAI to create a clear nature image prompt
/// 4. Sends the prompt to ComfyUI via ngrok
/// 5. Categorizes the prompt and retrieves a matching ambient sound
/// 6. Returns JSON with base64 encoded image AND sound (easy for Unity to parse)
/// 
/// Response format:
/// {
///   "success": true,
///   "originalTranscription": "...",
///   "enhancedPrompt": "...",
///   "negativePrompt": "...",
///   "category": "beach|forest|mountain|garden",
///   "image": "base64 encoded PNG",
///   "sound": "base64 encoded MP3",
///   "soundName": "beach_waves.mp3"
/// }
/// </summary>
public class AudioToImageWithSound
{
    private readonly ILogger<AudioToImageWithSound> _logger;
    private readonly HttpClient _httpClient;
    
    // ESP device control configuration
    private static readonly string EspEndpointBaseUrl = "https://espendpointacess.azurewebsites.net/api";
    
    private static string GetComfyUIUrl() =>
        Environment.GetEnvironmentVariable("ComfyUIUrl") ?? throw new InvalidOperationException("ComfyUIUrl not configured");
    private static readonly Dictionary<string, string> CategoryToDeviceMapping = new()
    {
        { "beach", "esp0-beach" },
        { "forest", "esp1-forest" },
        { "garden", "esp2-garden" },
        { "mountain", "esp3-mountain" }
    };

    public AudioToImageWithSound(ILogger<AudioToImageWithSound> logger, IHttpClientFactory httpClientFactory)
    {
        _logger = logger;
        _httpClient = httpClientFactory.CreateClient();
        _httpClient.Timeout = TimeSpan.FromMinutes(15); // ComfyUI can take longer with upscaling
    }

    [Function("AudioToImageWithSound")]
    public async Task<HttpResponseData> Run(
        [HttpTrigger(AuthorizationLevel.Function, "post", Route = "audio-to-image-with-sound")] HttpRequestData req)
    {
        _logger.LogInformation("AudioToImageWithSound function triggered");

        try
        {
            // Read audio file from request body
            using var memoryStream = new MemoryStream();
            await req.Body.CopyToAsync(memoryStream);
            var audioBytes = memoryStream.ToArray();

            if (audioBytes.Length == 0)
            {
                var badRequest = req.CreateResponse(System.Net.HttpStatusCode.BadRequest);
                await badRequest.WriteAsJsonAsync(new { success = false, error = "No audio file provided" });
                return badRequest;
            }

            _logger.LogInformation("Received audio file: {Size} bytes", audioBytes.Length);

            // Step 1: Convert audio to text using Azure Speech Service
            var transcribedText = await TranscribeAudioAsync(audioBytes);
            _logger.LogInformation("Transcribed text: {Text}", transcribedText);

            if (string.IsNullOrWhiteSpace(transcribedText))
            {
                var noSpeechResponse = req.CreateResponse(System.Net.HttpStatusCode.BadRequest);
                await noSpeechResponse.WriteAsJsonAsync(new { success = false, error = "Could not transcribe audio. Please speak clearly." });
                return noSpeechResponse;
            }

            // Step 2: Enhance the text using Azure OpenAI (generates both positive and negative prompts)
            var (enhancedPrompt, negativePrompt) = await EnhancePromptWithOpenAIAsync(transcribedText);
            _logger.LogInformation("Enhanced prompt: {Prompt}", enhancedPrompt);
            _logger.LogInformation("Negative prompt: {NegativePrompt}", negativePrompt);

            // Step 3: Categorize the prompt for sound selection and ESP trigger
            var category = CategorizePrompt(enhancedPrompt);
            _logger.LogInformation("Categorized as: {Category}", category);

            // Step 4: Generate 360° panorama image using ComfyUI
            _logger.LogInformation("Generating 360° panorama for prompt: {Prompt}", enhancedPrompt);
            
            var comfyClient = new ComfyUIClient(_httpClient, _logger, GetComfyUIUrl());

            var imageBytes = await comfyClient.GenerateImageAsync(
                prompt: enhancedPrompt,
                negativePrompt: negativePrompt,
                width: 2048,
                height: 1024,
                steps: 20,
                cfgScale: 6.0
            );

            _logger.LogInformation("360° panorama generated successfully: {Size} bytes", imageBytes.Length);

            // Step 5: Get sound URL for the category
            var soundUrl = $"https://endpoint-gtfbdtb7bwf2hsfb.westeurope-01.azurewebsites.net/api/sounds/{category}";
            _logger.LogInformation("Sound URL for category {Category}: {SoundUrl}", category, soundUrl);

            // Step 6: Trigger ESP device (non-blocking)
            _ = Task.Run(async () =>
            {
                try { await TriggerEspDeviceAsync(category); }
                catch { /* ignore */ }
            });

            // Step 7: Return the image directly (like AudioToImage) with metadata in headers
            // This is much simpler and more reliable than JSON with base64
            var response = req.CreateResponse(System.Net.HttpStatusCode.OK);
            response.Headers.Add("Content-Type", "image/png");
            response.Headers.Add("X-Original-Transcription", Convert.ToBase64String(Encoding.UTF8.GetBytes(transcribedText)));
            response.Headers.Add("X-Enhanced-Prompt", Convert.ToBase64String(Encoding.UTF8.GetBytes(enhancedPrompt)));
            response.Headers.Add("X-Negative-Prompt", Convert.ToBase64String(Encoding.UTF8.GetBytes(negativePrompt)));
            response.Headers.Add("X-Category", category);
            response.Headers.Add("X-Sound-Url", soundUrl);
            await response.Body.WriteAsync(imageBytes);
            
            _logger.LogInformation("Response sent successfully with image and sound URL in headers");
            return response;
        }
        catch (HttpRequestException httpEx)
        {
            _logger.LogError(httpEx, "Error connecting to ComfyUI service");
            var errorResponse = req.CreateResponse(System.Net.HttpStatusCode.ServiceUnavailable);
            await errorResponse.WriteAsJsonAsync(new 
            { 
                success = false,
                error = "ComfyUI service is unavailable. Check your ngrok connection.",
                details = httpEx.Message,
                comfyUIUrl = GetComfyUIUrl()
            });
            return errorResponse;
        }
        catch (Exception ex)
        {
            _logger.LogError(ex, "Error processing audio to image with sound");
            var errorResponse = req.CreateResponse(System.Net.HttpStatusCode.InternalServerError);
            await errorResponse.WriteAsJsonAsync(new { 
                success = false, 
                error = ex.Message,
                stackTrace = ex.StackTrace,
                innerError = ex.InnerException?.Message
            });
            return errorResponse;
        }
    }

    /// <summary>
    /// Transcribes audio bytes to text using Azure Speech Service
    /// </summary>
    private async Task<string> TranscribeAudioAsync(byte[] audioBytes)
    {
        var speechKey = Environment.GetEnvironmentVariable("SpeechServiceKey")
            ?? throw new InvalidOperationException("SpeechServiceKey not configured");
        var speechRegion = Environment.GetEnvironmentVariable("SpeechServiceRegion")
            ?? throw new InvalidOperationException("SpeechServiceRegion not configured");

        var speechConfig = SpeechConfig.FromSubscription(speechKey, speechRegion);
        speechConfig.SpeechRecognitionLanguage = "en-US";

        // Save audio to temp file (Speech SDK requires file or stream)
        var tempPath = Path.GetTempFileName() + ".wav";
        try
        {
            await File.WriteAllBytesAsync(tempPath, audioBytes);

            using var audioConfig = AudioConfig.FromWavFileInput(tempPath);
            using var recognizer = new SpeechRecognizer(speechConfig, audioConfig);

            var result = await recognizer.RecognizeOnceAsync();

            return result.Reason switch
            {
                ResultReason.RecognizedSpeech => result.Text,
                ResultReason.NoMatch => string.Empty,
                ResultReason.Canceled => throw new Exception($"Speech recognition canceled: {CancellationDetails.FromResult(result).ErrorDetails}"),
                _ => string.Empty
            };
        }
        finally
        {
            if (File.Exists(tempPath))
                File.Delete(tempPath);
        }
    }

    /// <summary>
    /// Enhances the transcribed text using Azure OpenAI to create model-specific positive and negative prompts
    /// </summary>
    private async Task<(string positivePrompt, string negativePrompt)> EnhancePromptWithOpenAIAsync(string transcribedText)
    {
        var openAIEndpoint = Environment.GetEnvironmentVariable("OpenAIEndpoint")
            ?? throw new InvalidOperationException("OpenAIEndpoint not configured");
        var openAIKey = Environment.GetEnvironmentVariable("OpenAIKey")
            ?? throw new InvalidOperationException("OpenAIKey not configured");

        var client = new AzureOpenAIClient(
            new Uri(openAIEndpoint),
            new ApiKeyCredential(openAIKey));

        // Use deployment name from environment variable (configure in Azure Portal)
        var deploymentName = Environment.GetEnvironmentVariable("OpenAIDeploymentName") ?? "gpt-4o-mini";
        var chatClient = client.GetChatClient(deploymentName);

        var systemPrompt = """
            You are a prompt engineer specializing in photorealistic 360-degree equirectangular panorama generation.
            
            TARGET MODEL: JuggernautXL v9 (SDXL-based photorealistic model)
            LORA: 360RedmondResized (specialized for seamless 360° panoramas)
            
            This model combination excels at:
            - Photorealistic imagery with exceptional detail and natural lighting
            - 360-degree equirectangular panoramas (2048x1024, 2:1 aspect ratio)
            - Natural landscapes: mountains, forests, lakes, oceans, valleys, meadows, deserts
            - Realistic lighting: golden hour, sunrise, sunset, natural daylight, moonlight
            - Atmospheric effects: mist, fog, volumetric lighting, god rays, atmospheric haze
            - Natural textures: rock formations, water reflections, vegetation details
            - Seamless wraparound panoramic continuity
            
            JuggernautXL responds well to:
            - Detailed scene descriptions with specific elements
            - Photography-style prompts (focal length, camera angle, exposure)
            - Natural lighting descriptors (soft light, rim light, backlit)
            - Texture and material descriptions
            - The 360RedmondResized LoRA trigger words for panoramic output
            
            YOUR TASK: Generate BOTH a positive prompt AND a context-aware negative prompt.
            
            POSITIVE PROMPT structure:
            1. Start with: "360 degree equirectangular panorama, 360 view, [landscape type]"
            2. Main subject with specific natural elements
            3. Lighting: time of day, light quality, sky conditions
            4. Atmosphere: weather, environmental conditions
            5. Details: textures, colors, depth
            6. End with: "photorealistic, highly detailed, seamless panorama, natural lighting, 8k, JuggernautXL style"
            
            NEGATIVE PROMPT should:
            - Include standard quality issues: blurry, low quality, artifacts, text, watermark, distorted
            - Include standard style exclusions: cartoon, anime, 3D render, CGI, illustration, painting
            - Include scene-specific exclusions based on what the user described
              (e.g., if user wants "beach" → exclude "snow, ice, winter, cold, mountains")
              (e.g., if user wants "forest" → exclude "desert, sand, ocean, beach, urban")
              (e.g., if user wants "night scene" → exclude "bright sunlight, harsh shadows, midday")
            - Always include: people, humans, person, buildings, urban, city, modern structures, roads, cars, indoor
            - Always include panorama issues: visible seams, warped edges, discontinuity, stitching artifacts
            
            OUTPUT FORMAT (JSON):
            {
              "positive": "your enhanced positive prompt here",
              "negative": "your context-aware negative prompt here"
            }
            
            Requirements:
            - Keep positive prompt under 120 words
            - Keep negative prompt under 80 words
            - Output ONLY valid JSON, no explanations
            """;

        var messages = new List<ChatMessage>
        {
            new SystemChatMessage(systemPrompt),
            new UserChatMessage($"Transform this into prompts for JuggernautXL + 360RedmondResized: {transcribedText}")
        };

        var response = await chatClient.CompleteChatAsync(messages);
        var responseText = response.Value.Content[0].Text.Trim();
        
        // Parse the JSON response
        try
        {
            var jsonDoc = JsonDocument.Parse(responseText);
            var positivePrompt = jsonDoc.RootElement.GetProperty("positive").GetString() ?? "";
            var negativePrompt = jsonDoc.RootElement.GetProperty("negative").GetString() ?? "";
            
            return (positivePrompt, negativePrompt);
        }
        catch (JsonException)
        {
            // Fallback: if JSON parsing fails, use the response as positive prompt with default negative
            _logger.LogWarning("Failed to parse AI response as JSON, using fallback. Response: {Response}", responseText);
            return (
                responseText,
                "people, humans, person, buildings, urban, city, cartoon, anime, 3D render, CGI, " +
                "blurry, low quality, artifacts, text, watermark, distorted, visible seams, " +
                "warped edges, discontinuity, stitching artifacts, modern structures, roads, cars, indoor"
            );
        }
    }

    /// <summary>
    /// Categorizes the enhanced prompt into one of the predefined scene categories
    /// </summary>
    private string CategorizePrompt(string enhancedPrompt)
    {
        var lowerPrompt = enhancedPrompt.ToLowerInvariant();
        
        // Score each category based on keyword matches
        int forestScore = 0;
        int beachScore = 0;
        int mountainScore = 0;
        int gardenScore = 0;
        
        // Forest keywords (weight: 2 for primary, 1 for secondary)
        if (lowerPrompt.Contains("forest")) forestScore += 3;
        if (lowerPrompt.Contains("woods") || lowerPrompt.Contains("woodland")) forestScore += 2;
        if (lowerPrompt.Contains("trees") || lowerPrompt.Contains("jungle")) forestScore += 1;
        
        // Beach keywords
        if (lowerPrompt.Contains("beach")) beachScore += 3;
        if (lowerPrompt.Contains("ocean") || lowerPrompt.Contains("sea")) beachScore += 2;
        if (lowerPrompt.Contains("shore") || lowerPrompt.Contains("coast") || lowerPrompt.Contains("sand")) beachScore += 1;
        
        // Mountain keywords
        if (lowerPrompt.Contains("mountain")) mountainScore += 3;
        if (lowerPrompt.Contains("peak") || lowerPrompt.Contains("summit") || lowerPrompt.Contains("alpine")) mountainScore += 2;
        if (lowerPrompt.Contains("cliff") || lowerPrompt.Contains("rocky")) mountainScore += 1;
        
        // Garden keywords
        if (lowerPrompt.Contains("garden")) gardenScore += 3;
        if (lowerPrompt.Contains("flower") || lowerPrompt.Contains("rose") || lowerPrompt.Contains("botanical")) gardenScore += 2;
        if (lowerPrompt.Contains("meadow") || lowerPrompt.Contains("bloom")) gardenScore += 1;
        
        // Find the highest score
        var maxScore = Math.Max(Math.Max(forestScore, beachScore), Math.Max(mountainScore, gardenScore));
        
        if (maxScore == 0)
        {
            // No clear category, default to forest
            _logger.LogInformation("No category keywords found, defaulting to forest");
            return "forest";
        }
        
        // Return the category with highest score (priority: forest > mountain > garden > beach if tied)
        if (forestScore == maxScore) return "forest";
        if (mountainScore == maxScore) return "mountain";
        if (gardenScore == maxScore) return "garden";
        if (beachScore == maxScore) return "beach";
        
        return "forest"; // Fallback
    }

    /// <summary>
    /// Triggers the appropriate ESP device based on the category
    /// </summary>
    private async Task TriggerEspDeviceAsync(string category)
    {
        try
        {
            _logger.LogInformation("Triggering ESP device for category: {Category}", category);
            
            // Get the device name from mapping
            if (!CategoryToDeviceMapping.TryGetValue(category, out var deviceName))
            {
                _logger.LogWarning("No device mapping found for category: {Category}", category);
                return;
            }
            
            // Build the ESP endpoint URL (5 minutes duration)
            var espUrl = $"{EspEndpointBaseUrl}/{deviceName}/5";
            _logger.LogInformation("Triggering ESP device: {Device} via {Url}", deviceName, espUrl);
            
            // Make the HTTP call to trigger the device
            var response = await _httpClient.GetAsync(espUrl);
            
            if (response.IsSuccessStatusCode)
            {
                _logger.LogInformation("Successfully triggered ESP device: {Device}", deviceName);
            }
            else
            {
                var errorContent = await response.Content.ReadAsStringAsync();
                _logger.LogWarning("ESP device trigger returned status {Status}: {Error}", 
                    response.StatusCode, errorContent);
            }
        }
        catch (Exception ex)
        {
            _logger.LogError(ex, "Error triggering ESP device");
            // Don't rethrow - this should not affect image generation
        }
    }
}

/// <summary>
/// Response model for AudioToImageWithSound - designed for easy Unity integration
/// Returns URLs to download image and sound separately (to avoid huge JSON responses)
/// </summary>
public class AudioToImageWithSoundResponse
{
    [JsonPropertyName("success")]
    public bool Success { get; set; }
    
    [JsonPropertyName("originalTranscription")]
    public string? OriginalTranscription { get; set; }
    
    [JsonPropertyName("enhancedPrompt")]
    public string? EnhancedPrompt { get; set; }
    
    [JsonPropertyName("negativePrompt")]
    public string? NegativePrompt { get; set; }
    
    [JsonPropertyName("category")]
    public string? Category { get; set; }
    
    [JsonPropertyName("imageUrl")]
    public string? ImageUrl { get; set; }  // URL to download the PNG image
    
    [JsonPropertyName("soundUrl")]
    public string? SoundUrl { get; set; }  // URL to download the MP3 sound
    
    [JsonPropertyName("soundName")]
    public string? SoundName { get; set; }
    
    [JsonPropertyName("message")]
    public string? Message { get; set; }
}
