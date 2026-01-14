using System.ClientModel;
using Azure.AI.OpenAI;
using Microsoft.Azure.Functions.Worker;
using Microsoft.Azure.Functions.Worker.Http;
using Microsoft.CognitiveServices.Speech;
using Microsoft.CognitiveServices.Speech.Audio;
using Microsoft.Extensions.Logging;
using OpenAI.Chat;

namespace dotnet_functions.Functions;

/// <summary>
/// HTTP trigger function that:
/// 1. Receives an audio file
/// 2. Converts speech to text using Azure Speech Service
/// 3. Enhances the text using Azure OpenAI to create a clear nature image prompt
/// </summary>
public class AudioToPrompt
{
    private readonly ILogger<AudioToPrompt> _logger;

    public AudioToPrompt(ILogger<AudioToPrompt> logger)
    {
        _logger = logger;
    }

    [Function("AudioToPrompt")]
    public async Task<HttpResponseData> Run(
        [HttpTrigger(AuthorizationLevel.Function, "post", Route = "audio-to-prompt")] HttpRequestData req)
    {
        _logger.LogInformation("AudioToPrompt function triggered");

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

            // Step 2: Enhance the text using Azure OpenAI
            var enhancedPrompt = await EnhancePromptWithOpenAIAsync(transcribedText);
            _logger.LogInformation("Enhanced prompt: {Prompt}", enhancedPrompt);

            // Return the result
            var response = req.CreateResponse(System.Net.HttpStatusCode.OK);
            await response.WriteAsJsonAsync(new
            {
                originalTranscription = transcribedText,
                enhancedPrompt = enhancedPrompt,
                message = "Audio successfully processed"
            });

            return response;
        }
        catch (Exception ex)
        {
            _logger.LogError(ex, "Error processing audio");
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
    /// Enhances the transcribed text using Azure OpenAI to create a clear, concise nature image prompt
    /// </summary>
    private async Task<string> EnhancePromptWithOpenAIAsync(string transcribedText)
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
            You are a prompt engineer specializing in photorealistic nature landscape generation using the CyberRealistic Stable Diffusion model.
            
            Your task: Transform spoken descriptions into detailed, photorealistic landscape prompts.
            
            The CyberRealistic model excels at:
            - Photorealistic natural landscapes (mountains, forests, lakes, oceans, valleys)
            - Realistic lighting (golden hour, sunrise, sunset, natural daylight, moonlight)
            - Atmospheric effects (mist, fog, clouds, rain, snow, atmospheric haze)
            - Natural textures (rock formations, water surfaces, vegetation, terrain)
            - Panoramic vistas and wide-angle nature scenes
            
            Prompt structure:
            1. Main subject: The landscape type and key natural elements
            2. Lighting: Time of day, light quality, shadows, highlights
            3. Atmosphere: Weather, air quality, environmental conditions
            4. Details: Specific textures, colors, depth, composition
            5. Style: Emphasize photorealistic, natural, high detail
            
            Requirements:
            - Keep under 75 words for optimal results
            - Use photographic and naturalistic language
            - Specify realistic lighting conditions
            - Avoid mentioning people, buildings, or man-made structures
            - Focus on natural elements only
            - Be specific with natural features (e.g., "pine forest" not just "forest")
            
            Output ONLY the enhanced prompt, nothing else.
            """;

        var messages = new List<ChatMessage>
        {
            new SystemChatMessage(systemPrompt),
            new UserChatMessage($"Transform this into a nature image prompt: {transcribedText}")
        };

        var response = await chatClient.CompleteChatAsync(messages);

        return response.Value.Content[0].Text.Trim();
    }
}
