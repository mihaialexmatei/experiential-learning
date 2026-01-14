using System.Net.Http.Headers;
using System.Text;
using System.Text.Json;
using System.Text.Json.Serialization;
using Microsoft.Azure.Functions.Worker;
using Microsoft.Azure.Functions.Worker.Http;
using Microsoft.Extensions.Logging;
using dotnet_functions.Services;

namespace dotnet_functions.Functions;

/// <summary>
/// HTTP trigger function that:
/// 1. Receives a text prompt
/// 2. Sends it to the ComfyUI service via ngrok
/// 3. Returns the generated image
/// </summary>
public class GenerateImage
{
    private readonly ILogger<GenerateImage> _logger;
    private readonly HttpClient _httpClient;
    private static readonly string ComfyUIUrl = 
        Environment.GetEnvironmentVariable("ComfyUIUrl") ?? throw new InvalidOperationException("ComfyUIUrl not configured");

    public GenerateImage(ILogger<GenerateImage> logger, IHttpClientFactory httpClientFactory)
    {
        _logger = logger;
        _httpClient = httpClientFactory.CreateClient();
        _httpClient.Timeout = TimeSpan.FromMinutes(15); // ComfyUI can take longer with upscaling
    }

    [Function("GenerateImage")]
    public async Task<HttpResponseData> Run(
        [HttpTrigger(AuthorizationLevel.Function, "post", Route = "generate-image")] HttpRequestData req)
    {
        _logger.LogInformation("GenerateImage function triggered");

        try
        {
            // Parse request body
            var requestBody = await new StreamReader(req.Body).ReadToEndAsync();
            var requestData = JsonSerializer.Deserialize<GenerateImageRequest>(requestBody);

            if (string.IsNullOrWhiteSpace(requestData?.Prompt))
            {
                var badRequest = req.CreateResponse(System.Net.HttpStatusCode.BadRequest);
                await badRequest.WriteAsJsonAsync(new { error = "Prompt is required" });
                return badRequest;
            }

            _logger.LogInformation("Generating image for prompt: {Prompt}", requestData.Prompt);

            // Create ComfyUI client
            var comfyClient = new ComfyUIClient(_httpClient, _logger, ComfyUIUrl);

            // Generate image using ComfyUI workflow
            var imageBytes = await comfyClient.GenerateImageAsync(
                prompt: requestData.Prompt,
                negativePrompt: requestData.NegativePrompt ?? 
                    "people, humans, person, buildings, urban, city, cartoonish, 3D, CGI, " +
                    "anime, blurry, low quality, overexposed, washed out, oversaturated, " +
                    "artificial colors, flat lighting, plastic-looking, grainy, artifacts, " +
                    "text, watermark, deform, glitch, noise",
                width: requestData.Width ?? 2048,
                height: requestData.Height ?? 1024,
                steps: requestData.NumInferenceSteps ?? 20,
                cfgScale: requestData.GuidanceScale ?? 6.0
            );

            _logger.LogInformation("Image generated successfully: {Size} bytes", imageBytes.Length);

            // Return the image
            var successResponse = req.CreateResponse(System.Net.HttpStatusCode.OK);
            successResponse.Headers.Add("Content-Type", "image/png");
            await successResponse.Body.WriteAsync(imageBytes);
            
            return successResponse;
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
            _logger.LogError(ex, "Error generating image");
            var errorResponse = req.CreateResponse(System.Net.HttpStatusCode.InternalServerError);
            await errorResponse.WriteAsJsonAsync(new { error = ex.Message });
            return errorResponse;
        }
    }
}

/// <summary>
/// Request model for image generation
/// </summary>
public class GenerateImageRequest
{
    [JsonPropertyName("prompt")]
    public string? Prompt { get; set; }
    
    [JsonPropertyName("negativePrompt")]
    public string? NegativePrompt { get; set; }
    
    [JsonPropertyName("width")]
    public int? Width { get; set; }
    
    [JsonPropertyName("height")]
    public int? Height { get; set; }
    
    [JsonPropertyName("numInferenceSteps")]
    public int? NumInferenceSteps { get; set; }
    
    [JsonPropertyName("guidanceScale")]
    public double? GuidanceScale { get; set; }
}
