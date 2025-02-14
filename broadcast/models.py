# models.py
from django.db import models

class Article(models.Model):
    title = models.CharField(max_length=255)
    source = models.CharField(max_length=255)
    url = models.URLField()
    published_at = models.DateTimeField()
    description = models.TextField()
    content = models.TextField()

    def __str__(self):
        return self.title
