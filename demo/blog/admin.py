from django.contrib import admin

from blog.models import Post, Customer, Order, OrderItem

admin.site.register(Post)
admin.site.register(Customer)
admin.site.register(Order)
admin.site.register(OrderItem)