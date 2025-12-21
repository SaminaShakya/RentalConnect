from django.shortcuts import render, redirect
from django.contrib.auth import login  
from .models import CustomUser, Profile
from .forms import ProfileForm

def register(request):
    if request.method == 'POST':
        username = request.POST['username']     
        email = request.POST['email']           
        password1 = request.POST['password1']   
        password2 = request.POST['password2']    
        phone = request.POST['phone']          
        user_type = request.POST.get('user_type', 'tenant') 
        
        if password1 == password2:
            try:
                user = CustomUser.objects.create_user(
                    username=username,    
                    email=email,          
                    password=password1,   
                    phone=phone           
                )
                if user_type == 'tenant':
                    user.is_tenant = True 
                else:
                    user.is_landlord = True 
                    
                user.save()  
                login(request, user)  

                # If landlord, redirect to profile form page
                if user.is_landlord:
                    return redirect('update_profile')
                
                # Otherwise redirect to dashboard
                return redirect('dashboard') 
                
            except Exception as e:
                return render(request, 'registration/register.html', {
                    'error': 'Username already exists or invalid data'
                })
        else:
            return render(request, 'registration/register.html', {
                'error': 'Passwords do not match'
            })
    
    return render(request, 'registration/register.html')


# View to create/update profile
def update_profile(request):
    profile, created = Profile.objects.get_or_create(user=request.user)
    
    if request.method == 'POST':
        form = ProfileForm(request.POST, request.FILES, instance=profile)
        if form.is_valid():
            form.save()
            return redirect('dashboard')
    else:
        form = ProfileForm(instance=profile)
    
    return render(request, 'users/update_profile.html', {'form': form})
