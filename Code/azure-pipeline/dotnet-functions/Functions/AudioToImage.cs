using System.ClientModel;
using System.Text;
using System.Text.Json;
using Azure.AI.OpenAI;
using Microsoft.Azure.Functions.Worker;
using Microsoft.Azure.Functions.Worker.Http;
using Microsoft.CognitiveServices.Speech;
using Microsoft.CognitiveServices.Speech.Audio;
using Microsoft.Extensions.Logging;
using OpenAI.Chat;
using dotnet_functions.Services;

namespace dotnet_functions.Functions;

/// <summary>
/// End-to-end HTTP trigger function that:
/// 1. Receives an audio file
/// 2. Converts speech to text using Azure Speech Service
/// 3. Enhances the text using Azure OpenAI to create a clear nature image prompt
/// 4. Sends the prompt to ComfyUI via ngrok
/// 5. Returns the generated 360° panorama image
/// </summary>
public class AudioToImage
{
    private readonly ILogger<AudioToImage> _logger;
    private readonly HttpClient _httpClient;
    private static readonly string ComfyUIUrl = 
        Environment.GetEnvironmentVariable("ComfyUIUrl") ?? throw new InvalidOperationException("ComfyUIUrl not configured");

    public AudioToImage(ILogger<AudioToImage> logger, IHttpClientFactory httpClientFactory)
    {
        _logger = logger;
        _httpClient = httpClientFactory.CreateClient();
        _httpClient.Timeout = TimeSpan.FromMinutes(15); // ComfyUI can take longer with upscaling
    }

    [Function("AudioToImage")]
    public async Task<HttpResponseData> Run(
        [HttpTrigger(AuthorizationLevel.Function, "post", Route = "audio-to-image")] HttpRequestData req)
    {
        _logger.LogInformation("AudioToImage function triggered");

        try
        {
            // Read audio file from request body
            using var memoryStream = new MemoryStream();
            await req.Body.CopyToAsync(memoryStream);
            var audioBytes = memoryStream.ToArray();

            if (audioBytes.Length == 0)
            {
                var badRequest = req.CreateResponse(System.Net.HttpStatusCode.BadRequest);
                await badRequest.WriteAsJsonAsync(new { error = "No audio file provided" });
                return badRequest;
            }

            _logger.LogInformation("Received audio file: {Size} bytes", audioBytes.Length);

            // Step 1: Convert audio to text using Azure Speech Service
            var transcribedText = await TranscribeAudioAsync(audioBytes);
            _logger.LogInformation("Transcribed text: {Text}", transcribedText);

            if (string.IsNullOrWhiteSpace(transcribedText))
            {
                var noSpeechResponse = req.CreateResponse(System.Net.HttpStatusCode.BadRequest);
                await noSpeechResponse.WriteAsJsonAsync(new { error = "Could not transcribe audio. Please speak clearly." });
                return noSpeechResponse;
            }

            // Step 2: Enhance the text using Azure OpenAI (generates both positive and negative prompts)
            var (enhancedPrompt, negativePrompt) = await EnhancePromptWithOpenAIAsync(transcribedText);
            _logger.LogInformation("Enhanced prompt: {Prompt}", enhancedPrompt);
            _logger.LogInformation("Negative prompt: {NegativePrompt}", negativePrompt);

            // Step 3: Generate 360° panorama image using ComfyUI
            _logger.LogInformation("Generating 360° panorama for prompt: {Prompt}", enhancedPrompt);
            
            var comfyClient = new ComfyUIClient(_httpClient, _logger, ComfyUIUrl);

            var imageBytes = await comfyClient.GenerateImageAsync(
                prompt: enhancedPrompt,
                negativePrompt: negativePrompt,
                width: 2048,
                height: 1024,
                steps: 20,
                cfgScale: 6.0
            );

            _logger.LogInformation("360° panorama generated successfully: {Size} bytes", imageBytes.Length);

            // Return the image with metadata in headers
            var response = req.CreateResponse(System.Net.HttpStatusCode.OK);
            response.Headers.Add("Content-Type", "image/png");
            response.Headers.Add("X-Original-Transcription", Convert.ToBase64String(Encoding.UTF8.GetBytes(transcribedText)));
            response.Headers.Add("X-Enhanced-Prompt", Convert.ToBase64String(Encoding.UTF8.GetBytes(enhancedPrompt)));
            response.Headers.Add("X-Negative-Prompt", Convert.ToBase64String(Encoding.UTF8.GetBytes(negativePrompt)));
            await response.Body.WriteAsync(imageBytes);
            
            return response;
        }
        catch (HttpRequestException httpEx)
        {
            _logger.LogError(httpEx, "Error connecting to ComfyUI service");
            var errorResponse = req.CreateResponse(System.Net.HttpStatusCode.ServiceUnavailable);
            await errorResponse.WriteAsJsonAsync(new 
            { 
                error = "ComfyUI service is unavailable. Check your ngrok connection.",
                details = httpEx.Message,
                comfyUIUrl = ComfyUIUrl
            });
            return errorResponse;
        }
        catch (Exception ex)
        {
            _logger.LogError(ex, "Error processing audio to image");
            var errorResponse = req.CreateResponse(System.Net.HttpStatusCode.InternalServerError);
            await errorResponse.WriteAsJsonAsync(new { error = ex.Message });
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
}