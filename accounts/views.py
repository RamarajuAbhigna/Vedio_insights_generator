from django.contrib.auth import authenticate, login, logout, get_user_model
from django.shortcuts import render, redirect, get_object_or_404
from django.contrib import messages
from django.contrib.auth.decorators import login_required
from django.core.mail import send_mail
from django.conf import settings
from .models import EmailOTP
import random

# get_user_model() correctly points to the User model in your models.py
User = get_user_model()

def login_view(request):
    if request.method == 'POST':
        email = request.POST.get('username')  # In your form, 'name' is 'username'
        password = request.POST.get('password')
        user = authenticate(request, email=email, password=password)

        if user:
            if not user.is_active:
                # Store user email in session so we can resend OTP if they try to login
                request.session['verify_user'] = user.id
                messages.error(request, 'Node not activated. Please verify your email.')
                return redirect('verify_otp')

            login(request, user)
            user.login_count += 1
            user.save()
            
            # ROLE-BASED REDIRECTION
            if user.role == 'admin':
                return redirect('admin_dashboard')
            return redirect('dashboard')
        else:
            messages.error(request, 'Invalid neural credentials.')

    return render(request, 'accounts/login.html')


def signup_view(request):
    if request.method == 'POST':
        email = request.POST.get('email')
        password = request.POST.get('password')

        if User.objects.filter(email=email).exists():
            messages.info(request, 'Neural identity already exists. Initialize login.')
            return redirect('login')

        # Create user with is_active=False until OTP is verified
        user = User.objects.create_user(
            email=email,
            password=password,
            is_active=False,
            role='user'
        )

        otp = str(random.randint(100000, 999999))
        EmailOTP.objects.update_or_create(user=user, defaults={'otp': otp})

        try:
            send_mail(
                'Verify your Neural Access Node',
                f'Your activation code is: {otp}',
                settings.EMAIL_HOST_USER,
                [email],
                fail_silently=False,
            )
            request.session['verify_user'] = user.id
            return redirect('verify_otp')
        except Exception as e:
            messages.error(request, "Mail transmission failed. Contact admin.")
            
    return render(request, 'accounts/signup.html')


def verify_otp_view(request):
    user_id = request.session.get('verify_user')
    if not user_id:
        return redirect('signup')

    user = get_object_or_404(User, id=user_id)

    if request.method == 'POST':
        entered_otp = request.POST.get('otp')
        otp_obj = EmailOTP.objects.filter(user=user).first()

        if otp_obj and not otp_obj.is_expired() and entered_otp == otp_obj.otp:
            user.is_active = True
            user.is_verified = True
            user.save()
            otp_obj.delete()
            # Success redirection: Use verify_success.html
            del request.session['verify_user']
            return render(request, 'accounts/verify_success.html', {'email': user.email})

        messages.error(request, 'Invalid or expired activation code.')

    return render(request, 'accounts/verify_otp.html')

def logout_view(request):
    logout(request)
    return redirect('landing')

@login_required
def profile_view(request):
    return render(request, 'accounts/profile.html')