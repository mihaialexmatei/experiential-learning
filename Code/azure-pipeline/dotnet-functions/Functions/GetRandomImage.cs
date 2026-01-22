using System.Net;
using Azure.Storage.Blobs;
using Azure.Storage.Blobs.Models;
using Microsoft.Azure.Functions.Worker;
using Microsoft.Azure.Functions.Worker.Http;
using Microsoft.Extensions.Logging;

namespace dotnet_functions.Functions;

/// <summary>
/// HTTP trigger function that retrieves a random image from Azure Blob Storage
/// based on the specified category (beach, mountain, forest, garden).
/// 
/// Usage:
///   GET /api/images/beach
///   GET /api/images/mountain
///   GET /api/images/forest
///   GET /api/images/garden
/// </summary>
public class GetRandomImage
{
    private readonly ILogger<GetRandomImage> _logger;
    private static readonly string StorageConnectionString = 
        Environment.GetEnvironmentVariable("StorageConnectionString") ?? 
        throw new InvalidOperationException("StorageConnectionString not configured");
    
    private static readonly string ContainerName = "premade-scenes";
    private static readonly string[] ValidCategories = { "beach", "mountain", "forest", "garden" };

    public GetRandomImage(ILogger<GetRandomImage> logger)
    {
        _logger = logger;
    }

    [Function("GetRandomImage")]
    public async Task<HttpResponseData> Run(
        [HttpTrigger(AuthorizationLevel.Anonymous, "get", Route = "images/{category}")] HttpRequestData req,
        string category)
    {
        _logger.LogInformation($"GetRandomImage function triggered for category: {category}");

        try
        {
            // Validate category
            if (string.IsNullOrWhiteSpace(category) || !ValidCategories.Contains(category.ToLower()))
            {
                _logger.LogWarning($"Invalid category requested: {category}");
                var badRequest = req.CreateResponse(HttpStatusCode.BadRequest);
                await badRequest.WriteAsJsonAsync(new 
                { 
                    error = "Invalid category",
                    message = $"Category must be one of: {string.Join(", ", ValidCategories)}",
                    validCategories = ValidCategories
                });
                return badRequest;
            }

            category = category.ToLower();
            _logger.LogInformation($"Searching for images with prefix: {category}_");

            // Connect to blob storage
            var blobServiceClient = new BlobServiceClient(StorageConnectionString);
            var containerClient = blobServiceClient.GetBlobContainerClient(ContainerName);

            // Check if container exists
            if (!await containerClient.ExistsAsync())
            {
                _logger.LogError($"Container '{ContainerName}' does not exist");
                var notFound = req.CreateResponse(HttpStatusCode.NotFound);
                await notFound.WriteAsJsonAsync(new 
                { 
                    error = "Container not found",
                    message = $"The blob container '{ContainerName}' does not exist"
                });
                return notFound;
            }

            // List all blobs with the category prefix
            var blobs = new List<string>();
            await foreach (var blobItem in containerClient.GetBlobsAsync(prefix: $"{category}_"))
            {
                // Only include PNG files
                if (blobItem.Name.EndsWith(".png", StringComparison.OrdinalIgnoreCase))
                {
                    blobs.Add(blobItem.Name);
                }
            }

            _logger.LogInformation($"Found {blobs.Count} images for category '{category}'");

            // Check if any blobs were found
            if (blobs.Count == 0)
            {
                _logger.LogWarning($"No images found for category: {category}");
                var notFound = req.CreateResponse(HttpStatusCode.NotFound);
                await notFound.WriteAsJsonAsync(new 
                { 
                    error = "No images found",
                    message = $"No images available for category '{category}'",
                    category = category
                });
                return notFound;
            }

            // Select a random blob
            var random = new Random();
            var randomBlobName = blobs[random.Next(blobs.Count)];
            _logger.LogInformation($"Selected random image: {randomBlobName}");

            // Download the blob
            var blobClient = containerClient.GetBlobClient(randomBlobName);
            var blobDownloadInfo = await blobClient.DownloadAsync();

            // Read the blob content
            using var memoryStream = new MemoryStream();
            await blobDownloadInfo.Value.Content.CopyToAsync(memoryStream);
            var imageBytes = memoryStream.ToArray();

            _logger.LogInformation($"Returning image: {randomBlobName} ({imageBytes.Length} bytes)");

            // Return the image
            var response = req.CreateResponse(HttpStatusCode.OK);
            response.Headers.Add("Content-Type", "image/png");
            response.Headers.Add("X-Image-Name", randomBlobName);
            response.Headers.Add("X-Category", category);
            response.Headers.Add("X-Total-Images", blobs.Count.ToString());
            response.Headers.Add("Cache-Control", "no-cache"); // Don't cache to ensure randomness
            await response.Body.WriteAsync(imageBytes);

            return response;
        }
        catch (Exception ex)
        {
            _logger.LogError(ex, $"Error retrieving random image for category '{category}'");
            var errorResponse = req.CreateResponse(HttpStatusCode.InternalServerError);
            await errorResponse.WriteAsJsonAsync(new 
            { 
                error = "Internal server error",
                message = "An error occurred while retrieving the image",
                details = ex.Message
            });
            return errorResponse;
        }
    }
}
