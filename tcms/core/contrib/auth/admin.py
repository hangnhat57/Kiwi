# -*- coding: utf-8 -*-

from django import forms
from django.urls import reverse
from django.contrib import admin
from django.http import HttpResponseRedirect
from django.contrib.auth.models import Permission, User
from django.contrib.auth.forms import UserChangeForm
from django.utils.translation import ugettext_lazy as _
from django.contrib.auth.admin import UserAdmin, sensitive_post_parameters_m


class MyUserChangeForm(UserChangeForm):
    """
        Enforces unique user emails.
    """
    email = forms.EmailField(required=True)

    def clean_email(self):
        qs = User.objects.filter(email=self.cleaned_data['email'])
        if self.instance:
            qs = qs.exclude(pk=self.instance.pk)
        if qs.count():
            raise forms.ValidationError(_('This email address is already in use'))
        else:
            return self.cleaned_data['email']


def _modifying_myself(request, object_id):
    return request.user.pk == int(object_id)


class KiwiUserAdmin(UserAdmin):
    list_display = UserAdmin.list_display + ('is_superuser', 'date_joined', 'last_login')
    ordering = ['-pk']  # same as -date_joined

    # override standard form and make the email address unique
    # even when adding users via admin panel
    form = MyUserChangeForm

    def has_change_permission(self, request, obj=None):
        return request.user.is_superuser or obj is not None

    def render_change_form(self, request, context, add=False, change=False, form_url='', obj=None):
        if not (_modifying_myself(request, obj.pk) or request.user.is_superuser):
            context.update({
                'show_save': False,
                'show_save_and_continue': False,
            })
        return super().render_change_form(request, context, add, change, form_url, obj)

    def get_readonly_fields(self, request, obj=None):
        if request.user.is_superuser:
            return super().get_readonly_fields(request, obj)

        readonly_fields = ['username', 'is_staff', 'is_active',
                           'is_superuser', 'last_login', 'date_joined',
                           'groups', 'user_permissions']
        if not _modifying_myself(request, obj.pk):
            readonly_fields.extend(['first_name', 'last_name', 'email'])

        return readonly_fields

    def get_fieldsets(self, request, obj=None):
        if request.user.is_superuser:
            return super().get_fieldsets(request, obj)

        first_fieldset_fields = ('username',)
        if _modifying_myself(request, obj.pk):
            first_fieldset_fields = first_fieldset_fields + ('password',)

        return ((None, {'fields': first_fieldset_fields}),
                (_('Personal info'), {'fields': ('first_name', 'last_name', 'email')}),
                (_('Permissions'), {'fields': ('is_active', 'groups')}))

    @sensitive_post_parameters_m
    def user_change_password(self, request, id, form_url=''):
        return HttpResponseRedirect(reverse('admin:password_change'))

    @admin.options.csrf_protect_m
    def delete_view(self, request, object_id, extra_context=None):
        if not _modifying_myself(request, object_id):
            return super().delete_view(request, object_id, extra_context)

        # allow deletion of the user own account
        permission = Permission.objects.get(content_type__app_label='auth',
                                            codename='delete_user')
        try:
            request.user.user_permissions.add(permission)
            return super().delete_view(request, object_id, extra_context)
        finally:
            request.user.user_permissions.remove(permission)

    def response_delete(self, request, obj_display, obj_id):
        result = super().response_delete(request, obj_display, obj_id)

        if not _modifying_myself(request, obj_id):
            return result

        # user doesn't exist anymore so go to the index page
        # instead of returning to the user admin page
        return HttpResponseRedirect(reverse('core-views-index'))

    def has_delete_permission(self, request, obj=None):
        # allow to delete yourself without having 'delete' permission
        # explicitly assigned
        if _modifying_myself(request, getattr(obj, 'pk', 0)):
            return True

        return super().has_delete_permission(request, obj)


# user admin extended functionality
admin.site.unregister(User)
admin.site.register(User, KiwiUserAdmin)
