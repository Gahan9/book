import json
from django.shortcuts import render, render_to_response
from django.http import HttpResponseRedirect, HttpResponse, Http404, request, JsonResponse
from django.contrib.auth.models import User
from django.contrib.auth.decorators import login_required
from django.core.mail import send_mail
from django.contrib.auth.tokens import PasswordResetTokenGenerator as activation_user
from django.template import loader
from django.urls import reverse
from django.db.models import Avg, Func
from decimal import Decimal
from operator import itemgetter

from .forms import SignUpForm, ChangePassword
from .models import *


class Round(Func):
    function = 'ROUND'
    template = '%(function)s(%(expressions)s, 1)'


@login_required(login_url='login/')
def index(request):
    """	Show all data from database """
    all_books = Book.objects.all().annotate(u_rating=Round(Avg('book_rating__rating'))).order_by('u_rating')
    context = {'bl': all_books}
    return render(request, 'book.html', context)


def delete_entry(request):
    if request.is_ajax():
        entry_id = json.loads(request.GET.get('entry_id'))
        book_to_delete = Book.objects.get(pk=entry_id)
        message = "Book " + book_to_delete.name + " with id: " + entry_id + " deleted successfully"
        book_to_delete.delete()
        data = {'message': message}
        return JsonResponse(data)
    else:
        data = {'message': 'Invalid Request'}
        return JsonResponse(data)


def stock_availability(request):
    if request.is_ajax():
        switch_id = request.GET.get('switch_id')
        switch_status = request.GET.get('switch_status')
        print(switch_status, switch_id, type(switch_status), sep=" ************ ")
        book = Book.objects.get(pk=switch_id)
        print("Before loop : ---------------->", book.availability)
        if switch_status == 'true':
            book.availability = True
            print("In if : ---------------->", book.availability)
        else:
            book.availability = False
            print("In else : ---------------->", book.availability)
        book.save()
        message = "Book: " + book.name + " id: " + str(switch_id) + " New status is : " + str(book.availability)
        data = {'message': message}
        return JsonResponse(data)
    else:
        data = {'message': 'Invalid Request'}
        return JsonResponse(data)


def register(request):
    if request.method == "POST":
        form = SignUpForm(request.POST)
        if form.is_valid():
            new_user_name = form.cleaned_data['username']
            new_user_password = form.cleaned_data['password1']
            new_user_email = form.cleaned_data['email']
            new_user = User.objects.create_user(username=new_user_name,
                                                email=new_user_email,
                                                password=new_user_password)
            new_user.is_active = False
            new_user.save()
            new_user_token = activation_user().make_token(new_user)
            # kwargs={'pk':new_user.id, 'token':new_user_token})
            host = request.get_host()
            # var_url = 'http://'+ host + url

            send_mail("Activate YOur Account",
                      loader.render_to_string('user_activate.html',
                                              {'pk': new_user.id,
                                               'token': new_user_token,
                                               'domain': host,
                                               'user': new_user_name}), 'test.gahan@gmail.com', ['gahan@quixom.com', new_user_email])
            return HttpResponseRedirect('/login/')
            # else:
            #     x = [v[0] for k, v in form.errors.items()]
            #     return HttpResponse(x)
    else:
        form = SignUpForm()
    return render(request, 'registration.html', {'form': form})


def activate_new_user(request, pk, token):
    usr = User.objects.get(pk=pk)
    verified = activation_user().check_token(usr, token)
    if verified:
        usr.is_active = True
        usr.save()
        return HttpResponseRedirect('/')
    else:
        return HttpResponse("Invalid Verification Link")


def change_password(request):
    if request.method == 'POST':
        current_user = request.user.username
        reset_form = ChangePassword(request.POST, user=request.user)
        if reset_form.is_valid():
            u = User.objects.get(username__exact=current_user)
            u.set_password(reset_form.cleaned_data['password2'])
            u.save()
            return HttpResponseRedirect('/')
    else:
        reset_form = ChangePassword(user=request.user)
    return render(request, 'change_password.html', {'reset_form': reset_form})


# @login_required(login_url='login/')
def product_page(request, book_id):
    product = Book.objects.get(pk=book_id)
    current_user = request.user
    rated_stat = BookRating.objects.filter(user=current_user, book__id=book_id).values()
    print(product, type(product), rated_stat, type(rated_stat))

    if request.method == "POST":
        current_user_rated = request.POST.get('user_rated', None)
        print(current_user_rated, type(current_user_rated), sep='\n')
        if current_user_rated:
            if not rated_stat.exists():
                now_rated = BookRating.objects.create(user=current_user,
                                       rating=int(current_user_rated),
                                       book=product)
                now_rated.save()
            else:
                return HttpResponse("You Have already Rated")
        else:
            pass

    if product:
        #Calculates Average Book Rating given by User
        filter_rating = BookRating.objects.filter(book_id=book_id).aggregate(avg_u_rating=Round(Avg('rating')))['avg_u_rating']

        #Calculates Publisher Rating
        pub_rating = Publisher.objects.annotate(pub_avg_rating=Round(Avg('book__book_rating__rating'))).filter(book__id=book_id)[0].pub_avg_rating

        #Calculates Author Rating
        auth_rating = Author.objects.annotate(author_avg_rating=Round(Avg('book__book_rating__rating'))).filter(book__id=book_id)

        context = {'p': product,
                   'user_rating': filter_rating,
                   'author_rating': auth_rating,
                   'publisher_rating': pub_rating,
                   }
        return render(request, 'book_page.html', context)
    else:
        error = 'You have encountered incorrect product page'
        return render(request, 'error.html', {'error': error})


def publisher_page(request, publisher_id):
    selected_publisher = Publisher.objects.get(pk=publisher_id).book_set.annotate(user_rating=Round(Avg('book_rating__rating'))).order_by('-published_date')

    selected_publisher_object = Publisher.objects.annotate(pub_avg_rating=Round(Avg('book__book_rating__rating'))).get(id=publisher_id)

    selected_author_object = Author.objects.annotate(author_avg_rating=Round(Avg('book__book_rating__rating')))

    try:
        context = {'selected_publisher': selected_publisher,
                   'selected_publisher_object': selected_publisher_object,
                   'selected_author': selected_author_object,
                   }
        return render(request, 'publisher_page.html', context)
    except selected_publisher_object.DoesNotExist:
        error = 'No author exist of this referance'
        return render(request, 'error.html', {'error': error})


def author_page(request, author_id):
    selected_author = Author.objects.get(pk=author_id).book_set.annotate(user_rating=Round(Avg('book_rating__rating'))).order_by('-published_date')

    selected_author_object = Author.objects.annotate(author_avg_rating=Round(Avg('book__book_rating__rating'))).get(id=author_id)

    selected_publisher_object = Publisher.objects.annotate(pub_avg_rating=Round(Avg('book__book_rating__rating')))
    try:
        context = {'selected_author': selected_author,
                   'selected_publisher_object': selected_publisher_object,
                   'selected_author_object': selected_author_object,
                   }
        return render(request, 'author_page.html', context)
    except selected_author_object.DoesNotExist:
        error = 'No author exist of this referance'
        return render(request, 'error.html', {'error': error})


def search(request):
    """ Implemented to sniff entries in database """
    ls = {"pk": request.GET.get('id', None),
          "name__icontains": request.GET.get('name', None),
          "author__name__icontains": request.GET.get('author', None),
          "pub__name__icontains": request.GET.get('publication', None)
          }

    req_data = dict(filter(lambda x: x[1], ls.items()))

    id_ = request.GET.get('id', None)

    if req_data:
        books = Book.objects.filter(**req_data)
        return render(request, 'results.html', {'books': books},
                      {'query': id_})
    else:
        error = 'No match found'
        return render(request, 'error.html', {'error': error})

