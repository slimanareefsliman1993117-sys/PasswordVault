from django.shortcuts import render, redirect, get_object_or_404
from django.contrib.auth.decorators import login_required
from django.http import JsonResponse
from .models import PasswordEntry, Category
from .forms import PasswordEntryForm, CategoryForm
from .utils import generate_password, check_password_strength, encrypt_password, decrypt_password
import logging


logger = logging.getLogger(__name__)
#========================================================================================
@login_required
def dashboard(request):
    logger.info(f"User {request.user.email} accessed vault dashboard")
    entries = PasswordEntry.objects.filter(user=request.user)
    categories = Category.objects.filter(user=request.user)
    return render(request, 'vault/dashboard.html', {'entries': entries, 'categories': categories})
#========================================================================================
@login_required
def add_password(request):
    logger.info(f"User {request.user.email} accessed add_password")
    if request.method == 'POST':
        form = PasswordEntryForm(request.POST, user=request.user)
        if form.is_valid():
            try:
                form.save(commit=True, user=request.user)
                logger.info(f"User {request.user.email} added new password entry")
                return redirect('vault:dashboard')
            except Exception as e:
                logger.error(f"Error adding entry for {request.user.email}: {str(e)}")
                form.add_error(None, "Unable to save. Please try again.")
        else:
            logger.warning(f"Form invalid for {request.user.email}: {form.errors}")
    else:
        form = PasswordEntryForm(user=request.user)
    return render(request, 'vault/add_password.html', {'form': form})
#========================================================================================
@login_required
def edit_password(request, pk):
    logger.info(f"User {request.user.email} accessed edit_password for pk={pk}")
    entry = get_object_or_404(PasswordEntry, pk=pk, user=request.user)
    if request.method == 'POST':
        form = PasswordEntryForm(request.POST, instance=entry, user=request.user)
        if form.is_valid():
            try:
                form.save(commit=True, user=request.user)
                logger.info(f"User {request.user.email} updated entry pk={pk}")
                return redirect('vault:dashboard')
            except Exception as e:
                logger.error(f"Error updating entry pk={pk} for {request.user.email}: {str(e)}")
                form.add_error(None, "Unable to save. Please try again.")
        else:
            logger.warning(f"Form invalid for {request.user.email}: {form.errors}")
    else:
        initial_password = decrypt_password(entry.encrypted_password)
        form = PasswordEntryForm(instance=entry, user=request.user, initial={'password': initial_password})
    return render(request, 'vault/edit_password.html', {'form': form, 'entry': entry})
#========================================================================================
@login_required
def delete_password(request, pk):
    logger.info(f"User {request.user.email} accessed delete_password for pk={pk}")
    entry = get_object_or_404(PasswordEntry, pk=pk, user=request.user)
    if request.method == 'POST':
        try:
            entry.delete()
            logger.info(f"User {request.user.email} deleted entry pk={pk}")
            return JsonResponse({'success': True})
        except Exception as e:
            logger.error(f"Error deleting entry pk={pk} for {request.user.email}: {str(e)}")
            return JsonResponse({'success': False, 'error': str(e)}, status=400)
    return JsonResponse({'success': False, 'error': 'Invalid request method'}, status=405)
#========================================================================================s
@login_required
def add_category(request):
    logger.info(f"User {request.user.email} accessed add_category")
    if request.method == 'POST':
        form = CategoryForm(request.POST)
        if form.is_valid():
            try:
                category = form.save(commit=False)
                category.user = request.user
                category.save()
                logger.info(f"User {request.user.email} added category: {category.name}")
                return redirect('vault:dashboard')
            except Exception as e:
                logger.error(f"Error adding category for {request.user.email}: {str(e)}")
                form.add_error(None, "Unable to save. Please try again.")
    else:
        form = CategoryForm()
    return render(request, 'vault/add_category.html', {'form': form})
#========================================================================================
@login_required
def edit_category(request, pk):
    logger.info(f"User {request.user.email} accessed edit_category for pk={pk}")
    category = get_object_or_404(Category, pk=pk, user=request.user)
    if request.method == 'POST':
        form = CategoryForm(request.POST, instance=category)
        if form.is_valid():
            try:
                form.save()
                logger.info(f"User {request.user.email} updated category pk={pk}")
                return redirect('vault:dashboard')
            except Exception as e:
                logger.error(f"Error updating category pk={pk} for {request.user.email}: {str(e)}")
                form.add_error(None, "Unable to save. Please try again.")
    else:
        form = CategoryForm(instance=category)
    return render(request, 'vault/edit_category.html', {'form': form, 'category': category})
#========================================================================================
@login_required
def delete_category(request, pk):
    logger.info(f"User {request.user.email} accessed delete_category for pk={pk}")
    category = get_object_or_404(Category, pk=pk, user=request.user)
    if request.method == 'POST':
        try:
            # Delete all associated password entries
            PasswordEntry.objects.filter(category=category, user=request.user).delete()
            category.delete()
            logger.info(f"User {request.user.email} deleted category pk={pk} and associated entries")
            return JsonResponse({'success': True})
        except Exception as e:
            logger.error(f"Error deleting category pk={pk} for {request.user.email}: {str(e)}")
            return JsonResponse({'success': False, 'error': str(e)}, status=400)
    return JsonResponse({'success': False, 'error': 'Invalid request method'}, status=405)
#========================================================================================
@login_required
def generate_password_view(request):
    logger.info(f"User {request.user.email} accessed generate_password")
    if request.method == 'POST':
        try:
            length = int(request.POST.get('length', 12))
            use_uppercase = request.POST.get('use_uppercase', 'true') == 'true'
            use_numbers = request.POST.get('use_numbers', 'true') == 'true'
            use_special = request.POST.get('use_special', 'true') == 'true'
            password = generate_password(
                length=length,
                use_uppercase=use_uppercase,
                use_numbers=use_numbers,
                use_special=use_special
            )
            return JsonResponse({'success': True, 'password': password})
        except Exception as e:
            logger.error(f"Error generating password for {request.user.email}: {str(e)}")
            return JsonResponse({'success': False, 'error': str(e)}, status=400)
    return JsonResponse({'success': False, 'error': 'Invalid request method'}, status=405)
#========================================================================================
@login_required
def check_strength(request):
    logger.info(f"User {request.user.email} accessed check_strength")
    if request.method == 'POST':
        try:
            password = request.POST.get('password', '')
            strength, feedback = check_password_strength(password)
            return JsonResponse({'success': True, 'strength': strength, 'feedback': feedback})
        except Exception as e:
            logger.error(f"Error checking strength for {request.user.email}: {str(e)}")
            return JsonResponse({'success': False, 'error': str(e)}, status=400)
    return JsonResponse({'success': False, 'error': 'Invalid request method'}, status=405)


@login_required
def reveal_password(request, pk):
    if request.method != 'POST':
        return JsonResponse({'success': False, 'error': 'POST required'}, status=405)
    entry = get_object_or_404(PasswordEntry, pk=pk, user=request.user)
    return JsonResponse({'success': True, 'password': decrypt_password(entry.encrypted_password)})
