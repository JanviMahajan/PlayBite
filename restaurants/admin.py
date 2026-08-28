from django.contrib import admin

from .models import RestaurantTable


@admin.register(RestaurantTable)
class RestaurantTableAdmin(admin.ModelAdmin):
    list_display = ('table_number', 'branch', 'is_active')
    list_filter = ('is_active', 'branch__restaurant')
    search_fields = ('table_number', 'branch__branch_name')
    list_select_related = ('branch',)
