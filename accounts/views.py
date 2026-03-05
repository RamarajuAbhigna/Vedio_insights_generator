from django.contrib.auth import authenticate, login, logout, get_user_model
from django.shortcuts import render, redirect, get_object_or_404
from django.contrib import messages
from django.contrib.auth.decorators import login_required
from django.core.mail import send_mail, EmailMultiAlternatives
from django.template.loader import render_to_string
from django.contrib.sites.shortcuts import get_current_site
from django.utils.http import urlsafe_base64_encode
from django.utils.encoding import force_bytes
from django.contrib.auth.tokens import default_token_generator
from django.conf import settings
from .models import EmailOTP
import random
from django.contrib.auth.password_validation import validate_password
from django.core.exceptions import ValidationError

User = get_user_model()


def login_view(request):
    if request.method == 'POST':
        email = request.POST.get('username')
        password = request.POST.get('password')
        user = authenticate(request, email=email, password=password)

        if user:
            if not user.is_active:
                request.session['verify_user'] = user.id
                messages.error(request, 'Node not activated. Please verify your email.')
                return redirect('verify_otp')

            login(request, user)
            user.login_count += 1
            user.save()

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

        try:
            validate_password(password)
        except ValidationError as e:
            messages.error(request, " ".join(e.messages))
            return render(request, 'accounts/signup.html')

        if User.objects.filter(email=email).exists():
            messages.info(request, 'Neural identity already exists. Initialize login.')
            return redirect('login')

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


# ✅ Custom Password Reset — Forces proper HTML email
def custom_password_reset(request):
    if request.method == 'POST':
        email = request.POST.get('email')
        try:
            user = User.objects.get(email=email)
            token = default_token_generator.make_token(user)
            uid = urlsafe_base64_encode(force_bytes(user.pk))
            domain = get_current_site(request).domain
            protocol = 'http'

            html_content = render_to_string('registration/password_reset_email.html', {
                'user': user,
                'uid': uid,
                'token': token,
                'domain': domain,
                'protocol': protocol,
            })

            msg = EmailMultiAlternatives(
                subject='Security Protocol Override: Reset Your Access Node',
                body='Please use an HTML-compatible email client to view this message.',
                from_email=settings.EMAIL_HOST_USER,
                to=[email]
            )
            msg.attach_alternative(html_content, "text/html")

            # TEMP DEBUG - write to file
            with open('test_email_output.html', 'w', encoding='utf-8') as f:
                f.write(html_content)
            print("✅ HTML written to test_email_output.html")

            msg.send()

        except User.DoesNotExist:
            pass

        return redirect('password_reset_done')

    return render(request, 'registration/password_reset_form.html')