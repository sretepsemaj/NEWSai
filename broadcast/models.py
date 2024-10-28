from django.db import models

class Article(models.Model):
    title = models.CharField(max_length=255)
    source = models.CharField(max_length=255)
    content = models.TextField()
    published_at = models.DateTimeField()
    author = models.CharField(max_length=255, blank=True, null=True)
    url = models.URLField()
    description = models.TextField(blank=True, null=True)
    image_url = models.URLField(blank=True, null=True)
    keywords = models.CharField(max_length=255, blank=True, null=True)
    date_extracted = models.DateTimeField(auto_now_add=True)  # Automatically set the extraction date

    def __str__(self):
        return self.title

class ArticleEmbedding(models.Model):
    article = models.OneToOneField(Article, on_delete=models.CASCADE, related_name='embedding')  # Link to the Article model
    vector = models.JSONField()  # Store the embedding vector as a JSON array
    created_at = models.DateTimeField(auto_now_add=True)  # When the embedding was created

    def __str__(self):
        return f"Embedding for {self.article.title}"

class ArticleGroq(models.Model):
    STATUS_CHOICES = [
        ('processed', 'Processed Successfully'),
        ('skipped', 'Skipped (Too Long)'),
    ]

    title = models.CharField(max_length=255)  # Article title
    polarized_content = models.TextField(blank=True, null=True)  # Processed content
    url = models.URLField()  # Link to the original article
    published_at = models.DateTimeField()  # Article's published date
    date_processed = models.DateTimeField(auto_now_add=True)  # Timestamp for processing
    status = models.CharField(
        max_length=10,
        choices=STATUS_CHOICES,
        default='processed'
    )  # Track processing status


class RepArticle(models.Model):
    title = models.CharField(max_length=255)
    summary = models.TextField()
    url = models.URLField()
    published_at = models.DateTimeField()
    created_at = models.DateTimeField(auto_now_add=True)  # Automatically set the field to now when the object is created

    def __str__(self):
        return self.title

class DemArticle(models.Model):
    title = models.CharField(max_length=255)
    summary = models.TextField()
    url = models.URLField()
    published_at = models.DateTimeField()
    created_at = models.DateTimeField(auto_now_add=True)

    def __str__(self):
        return self.title

