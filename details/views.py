import json

from django.contrib.auth.decorators import login_required
from django.contrib.messages.views import SuccessMessageMixin
from django.shortcuts import render, render_to_response
from django.http import HttpResponseRedirect, HttpResponse, Http404, request, JsonResponse
from django.core.mail import send_mail
from django.contrib.auth.tokens import PasswordResetTokenGenerator as activation_user
from django.template import loader
from django.core.urlresolvers import reverse_lazy
from django.utils.decorators import method_decorator
from django.views import View
from django.views.generic import ListView
from django.views.generic.detail import SingleObjectMixin
from django.views.generic.edit import CreateView, FormView, UpdateView, DeleteView, \
    FormMixin
from django.contrib import messages
from django.contrib.auth.mixins import LoginRequiredMixin
from django.contrib.auth.models import User, Group
from rest_framework import viewsets

from .serializers import UserSerializer, GroupSerializer, AuthorSerializer, BookSerializer, PublisherSerializer
from .forms import *
from .models import *


class UserViewSet(viewsets.ModelViewSet):
    """
    API endpoint that allows users to be viewed or edited.
    """
    queryset = User.objects.all().order_by('-date_joined')
    serializer_class = UserSerializer


class GroupViewSet(viewsets.ModelViewSet):
    """
    API endpoint that allows groups to be viewed or edited.
    """
    queryset = Group.objects.all()
    serializer_class = GroupSerializer


class AuthorViewSet(viewsets.ModelViewSet):
    """
    API endpoint that allows authors to be viewed or edited
    """
    queryset = Author.objects.all()
    serializer_class = AuthorSerializer


class BookViewSet(viewsets.ModelViewSet):
    """
    API endpoint that allows authors to be viewed or edited
    """
    queryset = Book.objects.all()
    serializer_class = BookSerializer


class PublisherViewSet(viewsets.ModelViewSet):
    """
    API endpoint that allows authors to be viewed or edited
    """
    queryset = Publisher.objects.all()
    serializer_class = PublisherSerializer


class Round(Func):
    function = 'ROUND'
    template = '%(function)s(%(expressions)s, 1)'


class HomePageView(LoginRequiredMixin, ListView, FormView):
    """	Show all data from database """
    login_url = 'login/'
    model = Book
    success_url = reverse_lazy('index')
    form_class = SearchBookForm
    template_name = 'book.html'
    queryset = Book.objects.all().annotate(u_rating=Round(Avg('book_rating__rating')))
    ordering = '-u_rating'

    def form_valid(self, form):
        author_name = form.cleaned_data['author']
        publisher_name = form.cleaned_data['pub']
        request_search = {
            'name__icontains': form.cleaned_data['name'],
            'author__name__icontains': author_name,
            'pub__name__icontains': publisher_name,
        }
        req_data = dict(filter(lambda x: x[1], request_search.items()))
        self.queryset = Book.objects.filter(**req_data)
        return render(self.request, 'results.html', {'object_list': self.queryset})


class BookCreate(SuccessMessageMixin, CreateView, FormMixin):
    template_name = 'book_create.html'
    form_class = AddBookForm
    success_url = reverse_lazy('index')
    success_message = "Book '%(name)s' was added to Inventory successfully!"

    def get_context_data(self, **kwargs):
        kwargs['form'] = self.get_form()
        context = {'page_title': 'Add New Book'}
        context.update(kwargs)
        return super(FormMixin, self).get_context_data(**context)


class BookEditView(SuccessMessageMixin, UpdateView):
    template_name = 'book_create.html'
    form_class = EditBookForm
    model = Book
    success_url = reverse_lazy('index')
    success_message = "Detail of '%(name)s' successfully updated!"

    def get_context_data(self, **kwargs):
        kwargs['form'] = self.get_form()
        context = {'page_title': 'Edit Book'}
        context.update(kwargs)
        return super(FormMixin, self).get_context_data(**context)


class BookDeleteView(SuccessMessageMixin, DeleteView):
    model = Book
    success_url = '/'
    success_message = "'%(name)s'  deleted..."

    def delete(self, request, *args, **kwargs):
        self.object = self.get_object()
        name = self.object.name
        request.session['name'] = name
        message = 'Book: ' + request.session['name'] + ' deleted successfully'
        messages.success(self.request, message)
        return super(BookDeleteView, self).delete(request, *args, **kwargs)


class ToggleStockAvailability(SuccessMessageMixin, View):
    def get(self, request):
        print(request.GET)
        switch_id = request.GET.get('switch_id')
        switch_status = request.GET.get('switch_status')
        if switch_status == 'true':
            switch_status = True
        else:
            switch_status = False
        Book.objects.filter(pk=switch_id).update(availability=switch_status)
        book = Book.objects.get(pk=switch_id)
        message = "Book: " + book.name + " id: " + str(switch_id) + " New status is : " + str(book.availability)
        data = {'message': message}
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
            host = request.get_host()

            send_mail("Activate YOur Account",
                      loader.render_to_string('user_activate.html',
                                              {'pk': new_user.id,
                                               'token': new_user_token,
                                               'domain': host,
                                               'user': new_user_name}), 'test.gahan@gmail.com', ['gahan@quixom.com', new_user_email])
            return HttpResponseRedirect('/login/')
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


class ChangeProfilePassword(FormView):
    form_class = ChangePassword
    success_url = reverse_lazy('login')
    template_name = 'change_password.html'

    def get_form_kwargs(self):
        kwargs = super(ChangeProfilePassword, self).get_form_kwargs()
        kwargs['user'] = self.request.user
        return kwargs

    def form_valid(self, form):
        form.save()
        messages.success(self.request, 'Your Password is changed successfully.')
        return super(ChangeProfilePassword, self).form_valid(form)

    def form_invalid(self, form):
        # messages.error(self.request, form.errors)
        return super(ChangeProfilePassword, self).form_invalid(form)

    @method_decorator(login_required)
    def dispatch(self, *args, **kwargs):
        return super(ChangeProfilePassword, self).dispatch(*args, **kwargs)


# @login_required(login_url='login/')
def product_page(request, book_id):
    product = Book.objects.get(pk=book_id)
    current_user = request.user
    rated_stat = BookRating.objects.filter(user=current_user, book__id=book_id).values()

    if request.method == "POST":
        current_user_rated = request.POST.get('user_rated', None)
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
                   'title': product.name,
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
                   'title': selected_publisher_object.name,
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
                   'title': selected_author_object.name,
                   }
        return render(request, 'author_page.html', context)
    except selected_author_object.DoesNotExist:
        error = 'No author exist of this referance'
        return render(request, 'error.html', {'error': error})
