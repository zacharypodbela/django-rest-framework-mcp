from django.contrib import admin

from blog.models import Customer, Order, OrderItem, Post

admin.site.register(Post)
admin.site.register(Customer)
admin.site.register(Order)
admin.site.register(OrderItem)
