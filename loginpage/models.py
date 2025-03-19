from django.db import models

# Create your models here.
#THIS IS FOR DATABASE BTW
class TestModel(models.Model):
    title = models.CharField(max_length=75)
    body = models.TextField()
    slug = models.SlugField()
    date = models.DateTimeField(auto_now_add=True) #datetime stamp is added every new record 
    