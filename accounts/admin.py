from django.contrib import admin

from .models import User


@admin.register(User)
class UserAdmin(admin.ModelAdmin):
    list_display = ('email', 'full_name', 'role', 'is_staff', 'is_active')
    list_filter = ('role', 'is_staff', 'is_active', 'is_superuser')
    search_fields = ('email', 'full_name')
    readonly_fields = ('date_joined',)
    fieldsets = (
        ('Account', {'fields': ('email', 'password', 'full_name', 'role')}),
        ('Permissions', {'fields': ('is_active', 'is_staff', 'is_superuser', 'groups', 'user_permissions')}),
        ('Dates', {'fields': ('last_login', 'date_joined')}),
    )
