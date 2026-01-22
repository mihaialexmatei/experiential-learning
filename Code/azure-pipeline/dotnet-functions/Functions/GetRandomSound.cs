using System.Net;
using Azure.Storage.Blobs;
using Azure.Storage.Blobs.Models;
using Microsoft.Azure.Functions.Worker;
using Microsoft.Azure.Functions.Worker.Http;
using Microsoft.Extensions.Logging;

namespace dotnet_functions.Functions;

/// <summary>
/// HTTP trigger function that retrieves a random ambient sound from Azure Blob Storage
/// based on the specified category (beach, mountain, forest, garden).
/// 
/// Usage:
///   GET /api/sounds/beach
///   GET /api/sounds/mountain
///   GET /api/sounds/forest
///   GET /api/sounds/garden
/// </summary>
public class GetRandomSound
{
    private readonly ILogger<GetRandomSound> _logger;
    private static readonly string ContainerName = "sounds";
    private static readonly string[] ValidCategories = { "beach", "mountain", "forest", "garden" };

    private static string GetStorageConnectionString()
    {
        return Environment.GetEnvironmentVariable("StorageConnectionString") 
            ?? throw new InvalidOperationException("StorageConnectionString not configured");
    }

    public GetRandomSound(ILogger<GetRandomSound> logger)
    {
        _logger = logger;
    }

    [Function("GetRandomSound")]
    public async Task<HttpResponseData> Run(
        [HttpTrigger(AuthorizationLevel.Anonymous, "get", Route = "sounds/{category}")] HttpRequestData req,
        string category)
    {
        _logger.LogInformation($"GetRandomSound function triggered for category: {category}");

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
            _logger.LogInformation($"Searching for sounds with prefix: {category}_");

            // Connect to blob storage
            var blobServiceClient = new BlobServiceClient(GetStorageConnectionString());
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
                // Only include MP3 files
                if (blobItem.Name.EndsWith(".mp3", StringComparison.OrdinalIgnoreCase))
                {
                    blobs.Add(blobItem.Name);
                }
            }

            _logger.LogInformation($"Found {blobs.Count} sounds for category '{category}'");

            // Check if any blobs were found
            if (blobs.Count == 0)
            {
                _logger.LogWarning($"No sounds found for category: {category}");
                var notFound = req.CreateResponse(HttpStatusCode.NotFound);
                await notFound.WriteAsJsonAsync(new 
                { 
                    error = "No sounds found",
                    message = $"No sounds available for category '{category}'",
                    category = category
                });
                return notFound;
            }

            // Select a random blob
            var random = new Random();
            var randomBlobName = blobs[random.Next(blobs.Count)];
            _logger.LogInformation($"Selected random sound: {randomBlobName}");

            // Download the blob
            var blobClient = containerClient.GetBlobClient(randomBlobName);
            var blobDownloadInfo = await blobClient.DownloadAsync();

            // Read the blob content
            using var memoryStream = new MemoryStream();
            await blobDownloadInfo.Value.Content.CopyToAsync(memoryStream);
            var soundBytes = memoryStream.ToArray();

            _logger.LogInformation($"Returning sound: {randomBlobName} ({soundBytes.Length} bytes)");

            // Return the sound file
            var response = req.CreateResponse(HttpStatusCode.OK);
            response.Headers.Add("Content-Type", "audio/mpeg");
            response.Headers.Add("X-Sound-Name", randomBlobName);
            response.Headers.Add("X-Category", category);
            response.Headers.Add("X-Total-Sounds", blobs.Count.ToString());
            response.Headers.Add("Cache-Control", "no-cache"); // Don't cache to ensure randomness
            await response.Body.WriteAsync(soundBytes);

            return response;
        }
        catch (Exception ex)
        {
            _logger.LogError(ex, $"Error retrieving random sound for category '{category}'");
            var errorResponse = req.CreateResponse(HttpStatusCode.InternalServerError);
            await errorResponse.WriteAsJsonAsync(new 
            { 
                error = "Internal server error",
                message = "An error occurred while retrieving the sound",
                details = ex.Message
            });
            return errorResponse;
        }
    }

    /// <summary>
    /// Static helper method to get a random sound for a category.
    /// Used by AudioToImageWithSound to include sound in the response.
    /// </summary>
    public static async Task<(byte[] soundBytes, string soundName)?> GetRandomSoundForCategoryAsync(
        string category, 
        ILogger logger)
    {
        try
        {
            var storageConnectionString = Environment.GetEnvironmentVariable("StorageConnectionString") 
                ?? throw new InvalidOperationException("StorageConnectionString not configured");
            
            var blobServiceClient = new BlobServiceClient(storageConnectionString);
            var containerClient = blobServiceClient.GetBlobContainerClient(ContainerName);

            if (!await containerClient.ExistsAsync())
            {
                logger.LogWarning($"Sound container '{ContainerName}' does not exist");
                return null;
            }

            // List all blobs with the category prefix
            var blobs = new List<string>();
            await foreach (var blobItem in containerClient.GetBlobsAsync(prefix: $"{category}_"))
            {
                if (blobItem.Name.EndsWith(".mp3", StringComparison.OrdinalIgnoreCase))
                {
                    blobs.Add(blobItem.Name);
                }
            }

            if (blobs.Count == 0)
            {
                logger.LogWarning($"No sounds found for category: {category}");
                return null;
            }

            // Select a random blob
            var random = new Random();
            var randomBlobName = blobs[random.Next(blobs.Count)];
            logger.LogInformation($"Selected random sound for combined response: {randomBlobName}");

            // Download the blob
            var blobClient = containerClient.GetBlobClient(randomBlobName);
            var blobDownloadInfo = await blobClient.DownloadAsync();

            using var memoryStream = new MemoryStream();
            await blobDownloadInfo.Value.Content.CopyToAsync(memoryStream);
            
            return (memoryStream.ToArray(), randomBlobName);
        }
        catch (Exception ex)
        {
            logger.LogError(ex, $"Error getting random sound for category '{category}'");
            return null;
        }
    }
}
