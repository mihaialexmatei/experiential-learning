using System.Text;
using System.Text.Json;
using System.Text.Json.Serialization;
using Microsoft.Extensions.Logging;

namespace dotnet_functions.Services;

/// <summary>
/// Client for interacting with ComfyUI API via ngrok
/// </summary>
public class ComfyUIClient
{
    private readonly HttpClient _httpClient;
    private readonly ILogger _logger;
    private readonly string _baseUrl;
    private readonly string _workflowTemplate;

    /// <summary>
    /// Create ComfyUIClient with embedded workflow template
    /// </summary>
    public ComfyUIClient(HttpClient httpClient, ILogger logger, string baseUrl)
    {
        _httpClient = httpClient;
        _logger = logger;
        _baseUrl = baseUrl.TrimEnd('/');
        _workflowTemplate = WorkflowTemplate.Json;
    }

    /// <summary>
    /// Generate an image using the ComfyUI workflow
    /// </summary>
    public async Task<byte[]> GenerateImageAsync(
        string prompt,
        string negativePrompt,
        int width = 2048,
        int height = 1024,
        int steps = 20,
        double cfgScale = 6.0,
        long? seed = null)
    {
        try
        {
            // Parse the workflow template
            var workflow = JsonSerializer.Deserialize<Dictionary<string, JsonElement>>(_workflowTemplate);
            if (workflow == null)
                throw new Exception("Failed to parse workflow template");

            // Generate random seed if not provided
            var useSeed = seed ?? new Random().NextInt64(0, long.MaxValue);

            // Update the workflow with our parameters
            workflow = UpdateWorkflowParameters(workflow, prompt, negativePrompt, width, height, steps, cfgScale, useSeed);

            // Submit the workflow to ComfyUI
            var promptId = await SubmitWorkflowAsync(workflow);
            _logger.LogInformation("ComfyUI prompt submitted: {PromptId}", promptId);

            // Poll for completion and get the result
            var imageBytes = await PollForCompletionAsync(promptId);
            _logger.LogInformation("ComfyUI image generation completed: {Size} bytes", imageBytes.Length);

            return imageBytes;
        }
        catch (Exception ex)
        {
            _logger.LogError(ex, "Error generating image with ComfyUI");
            throw;
        }
    }

    /// <summary>
    /// Update workflow parameters with user inputs
    /// </summary>
    private Dictionary<string, JsonElement> UpdateWorkflowParameters(
        Dictionary<string, JsonElement> workflow,
        string prompt,
        string negativePrompt,
        int width,
        int height,
        int steps,
        double cfgScale,
        long seed)
    {
        // Node 3: Positive prompt
        if (workflow.ContainsKey("3"))
        {
            var node3 = JsonSerializer.Deserialize<Dictionary<string, JsonElement>>(workflow["3"].GetRawText());
            if (node3 != null && node3.ContainsKey("inputs"))
            {
                var inputs = JsonSerializer.Deserialize<Dictionary<string, JsonElement>>(node3["inputs"].GetRawText());
                if (inputs != null)
                {
                    inputs["text"] = JsonSerializer.SerializeToElement(prompt);
                    node3["inputs"] = JsonSerializer.SerializeToElement(inputs);
                    workflow["3"] = JsonSerializer.SerializeToElement(node3);
                }
            }
        }

        // Node 4: Negative prompt
        if (workflow.ContainsKey("4"))
        {
            var node4 = JsonSerializer.Deserialize<Dictionary<string, JsonElement>>(workflow["4"].GetRawText());
            if (node4 != null && node4.ContainsKey("inputs"))
            {
                var inputs = JsonSerializer.Deserialize<Dictionary<string, JsonElement>>(node4["inputs"].GetRawText());
                if (inputs != null)
                {
                    inputs["text"] = JsonSerializer.SerializeToElement(negativePrompt);
                    node4["inputs"] = JsonSerializer.SerializeToElement(inputs);
                    workflow["4"] = JsonSerializer.SerializeToElement(node4);
                }
            }
        }

        // Node 7: Empty Latent Image (width/height)
        if (workflow.ContainsKey("7"))
        {
            var node7 = JsonSerializer.Deserialize<Dictionary<string, JsonElement>>(workflow["7"].GetRawText());
            if (node7 != null && node7.ContainsKey("inputs"))
            {
                var inputs = JsonSerializer.Deserialize<Dictionary<string, JsonElement>>(node7["inputs"].GetRawText());
                if (inputs != null)
                {
                    inputs["width"] = JsonSerializer.SerializeToElement(width);
                    inputs["height"] = JsonSerializer.SerializeToElement(height);
                    node7["inputs"] = JsonSerializer.SerializeToElement(inputs);
                    workflow["7"] = JsonSerializer.SerializeToElement(node7);
                }
            }
        }

        // Node 8: KSampler (steps, cfg, seed)
        if (workflow.ContainsKey("8"))
        {
            var node8 = JsonSerializer.Deserialize<Dictionary<string, JsonElement>>(workflow["8"].GetRawText());
            if (node8 != null && node8.ContainsKey("inputs"))
            {
                var inputs = JsonSerializer.Deserialize<Dictionary<string, JsonElement>>(node8["inputs"].GetRawText());
                if (inputs != null)
                {
                    inputs["steps"] = JsonSerializer.SerializeToElement(steps);
                    inputs["cfg"] = JsonSerializer.SerializeToElement(cfgScale);
                    inputs["seed"] = JsonSerializer.SerializeToElement(seed);
                    node8["inputs"] = JsonSerializer.SerializeToElement(inputs);
                    workflow["8"] = JsonSerializer.SerializeToElement(node8);
                }
            }
        }

        // Node 11: Ultimate SD Upscale (seed)
        if (workflow.ContainsKey("11"))
        {
            var node11 = JsonSerializer.Deserialize<Dictionary<string, JsonElement>>(workflow["11"].GetRawText());
            if (node11 != null && node11.ContainsKey("inputs"))
            {
                var inputs = JsonSerializer.Deserialize<Dictionary<string, JsonElement>>(node11["inputs"].GetRawText());
                if (inputs != null)
                {
                    inputs["seed"] = JsonSerializer.SerializeToElement(seed);
                    node11["inputs"] = JsonSerializer.SerializeToElement(inputs);
                    workflow["11"] = JsonSerializer.SerializeToElement(node11);
                }
            }
        }

        return workflow;
    }

    /// <summary>
    /// Submit workflow to ComfyUI queue
    /// </summary>
    private async Task<string> SubmitWorkflowAsync(Dictionary<string, JsonElement> workflow)
    {
        var payload = new
        {
            prompt = workflow,
            client_id = Guid.NewGuid().ToString()
        };

        var jsonContent = new StringContent(
            JsonSerializer.Serialize(payload),
            Encoding.UTF8,
            "application/json");

        var response = await _httpClient.PostAsync($"{_baseUrl}/prompt", jsonContent);
        
        if (!response.IsSuccessStatusCode)
        {
            var error = await response.Content.ReadAsStringAsync();
            throw new Exception($"Failed to submit workflow: {response.StatusCode} - {error}");
        }

        var responseContent = await response.Content.ReadAsStringAsync();
        var result = JsonSerializer.Deserialize<Dictionary<string, JsonElement>>(responseContent);
        
        if (result == null || !result.ContainsKey("prompt_id"))
            throw new Exception("Invalid response from ComfyUI");

        return result["prompt_id"].GetString() ?? throw new Exception("No prompt_id in response");
    }

    /// <summary>
    /// Poll for workflow completion and retrieve the generated image
    /// </summary>
    private async Task<byte[]> PollForCompletionAsync(string promptId, int maxAttempts = 120, int delaySeconds = 5)
    {
        for (int i = 0; i < maxAttempts; i++)
        {
            try
            {
                // Check queue status
                var historyResponse = await _httpClient.GetAsync($"{_baseUrl}/history/{promptId}");
                
                if (historyResponse.IsSuccessStatusCode)
                {
                    var historyContent = await historyResponse.Content.ReadAsStringAsync();
                    var history = JsonSerializer.Deserialize<Dictionary<string, JsonElement>>(historyContent);

                    if (history != null && history.ContainsKey(promptId))
                    {
                        var promptData = history[promptId];
                        
                        // Check if completed
                        if (promptData.TryGetProperty("outputs", out var outputs))
                        {
                            // Find the SaveImage node output (node 12 in our workflow)
                            if (outputs.TryGetProperty("12", out var saveImageOutput))
                            {
                                if (saveImageOutput.TryGetProperty("images", out var images))
                                {
                                    var imageArray = images.EnumerateArray().ToList();
                                    if (imageArray.Count > 0)
                                    {
                                        var firstImage = imageArray[0];
                                        if (firstImage.TryGetProperty("filename", out var filenameElement))
                                        {
                                            var filename = filenameElement.GetString();
                                            var subfolder = firstImage.TryGetProperty("subfolder", out var subfolderElement) 
                                                ? subfolderElement.GetString() 
                                                : "";
                                            var type = firstImage.TryGetProperty("type", out var typeElement)
                                                ? typeElement.GetString()
                                                : "output";

                                            // Download the image
                                            return await DownloadImageAsync(filename, subfolder, type);
                                        }
                                    }
                                }
                            }
                        }
                    }
                }

                // Wait before next poll
                _logger.LogInformation("ComfyUI generation in progress... (attempt {Attempt}/{MaxAttempts})", i + 1, maxAttempts);
                await Task.Delay(TimeSpan.FromSeconds(delaySeconds));
            }
            catch (Exception ex)
            {
                _logger.LogWarning(ex, "Error polling ComfyUI status (attempt {Attempt})", i + 1);
                await Task.Delay(TimeSpan.FromSeconds(delaySeconds));
            }
        }

        throw new TimeoutException($"ComfyUI generation timed out after {maxAttempts * delaySeconds} seconds");
    }

    /// <summary>
    /// Download the generated image from ComfyUI
    /// </summary>
    private async Task<byte[]> DownloadImageAsync(string? filename, string? subfolder, string? type)
    {
        var url = $"{_baseUrl}/view?filename={Uri.EscapeDataString(filename ?? "")}";
        
        if (!string.IsNullOrEmpty(subfolder))
            url += $"&subfolder={Uri.EscapeDataString(subfolder)}";
        
        if (!string.IsNullOrEmpty(type))
            url += $"&type={Uri.EscapeDataString(type)}";

        _logger.LogInformation("Downloading image from: {Url}", url);

        var response = await _httpClient.GetAsync(url);
        
        if (!response.IsSuccessStatusCode)
            throw new Exception($"Failed to download image: {response.StatusCode}");

        return await response.Content.ReadAsByteArrayAsync();
    }
}
