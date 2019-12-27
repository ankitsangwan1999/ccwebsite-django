from django.shortcuts import render, get_object_or_404, reverse, HttpResponseRedirect, HttpResponse
from django.http import JsonResponse
from django.contrib.auth.decorators import login_required
from django.core.paginator import Paginator  # EmptyPage, PageNotAnInteger
from django.contrib import messages
from django.contrib.auth import get_user_model
from django.contrib.auth.models import Group
from django.db.models import Count
from django.utils.timesince import timesince
from django.utils import timezone
from django.contrib.sites.models import Site

# from django.contrib.sites.shortcuts import get_current_site

# from django.contrib.contenttypes.models import ContentType
# from django.views.generic import RedirectView

# Imports for notification
from channels.layers import get_channel_layer
from asgiref.sync import async_to_sync
import json

# Imports for Email
from django.core import mail
from django.template.loader import render_to_string
from django.utils.html import strip_tags


# Imported Models
from user_profile.models import UserProfile
from .models import Post, Tags, PostView
from comments.models import Comment
# from notifications.models import Notification
# from comments.models import Comment

# Imported Forms
from comments.forms import CommentForm
from home.forms import UserSignupForm
# from .forms import PostForm

# 3rd Party imports
# from notifications.signals import notify
# from notify.signals import notify

# Self imports
# from home.views import set_profile

NUMBER_OF_POSTS_PER_PAGE = 5
User = get_user_model()


def page_maker(request, model, native_user=None, draft=False, tag_filter=None, username=None, liked=None, older=None, *args, **kwargs):
    """
        Function to make pages taking NUMBER_OF_POSTS_PER_PAGE in one page.
    """
    if username:
        # Posts for personalised feed.
        user_qs = User.objects.filter(username=username)
        user = user_qs.first()
        profile = UserProfile.objects.get(user=user)
        followed = profile.followed_users.all() | user_qs
        if tag_filter:
            tag_qs = Tags.objects.filter(name=tag_filter)
            if tag_qs:
                # Filter posts by a tag and verify_status = 1 (i.e. Verified by Admin)
                tag = tag_qs.first()
                post_list = model.objects.all(
                    native_user=native_user,
                    draft=draft
                ).filter(verify_status=1).filter(tags=tag).filter(author__in=followed)
            else:
                # All drafts filtered by verify_status = 1 (i.e. Verified by Admin)
                post_list = model.objects.all(
                    native_user=native_user,
                    draft=draft).filter(verify_status=1).filter(author__in=followed)
                messages.error(request, f"Oops, Something went wrong!")
        else:
            # All posts filtered by verify_status = 1 (i.e. Verified by Admin)
            post_list = model.objects.all(
                native_user=native_user,
                draft=draft).filter(verify_status=1).filter(author__in=followed)
    else:
        # Posts for Public feed
        if tag_filter:
            tag_qs = Tags.objects.filter(name=tag_filter)
            if tag_qs:
                # Filter posts by a tag and verify_status = 1 (i.e. Verified by Admin)
                tag = tag_qs.first()
                post_list = model.objects.all(native_user=native_user, draft=draft).filter(verify_status=1).filter(tags=tag)
            else:
                # All drafts filtered by verify_status = 1 (i.e. Verified by Admin)
                post_list = model.objects.all(native_user=native_user, draft=draft).filter(verify_status=1)
                messages.error(request, f"Oops, Something went wrong!")
        else:
            # All posts filtered by verify_status = 1 (i.e. Verified by Admin)
            post_list = model.objects.all(native_user=native_user, draft=draft).filter(verify_status=1)

    if liked is not None:
        # Order by most liked posts.
        post_list = post_list.annotate(like_count=Count('likes')).order_by('-like_count')
    if older is not None:
        # Order by older posts first.
        post_list = post_list.order_by('published')
    paginator = Paginator(post_list, NUMBER_OF_POSTS_PER_PAGE)
    page = request.GET.get('page')
    return paginator.get_page(page)


@login_required
def ajax_add_post(request):
    """
        Function to add post and send it for approval using AJAX.
    """
    if request.method == "POST":

        # Title of post
        title = request.POST['title']

        # Tags, appended to each other
        tags_str = request.POST['tags']
        tags_str = str(tags_str)

        # Post content
        post_content = request.POST['post_content']

        # Whether this post is draft/scheduled or not
        is_draft = request.POST['is_draft']
        is_scheduled = request.POST['is_scheduled']

        # Current user and his/her User Profile
        user = request.user
        user_profile = get_object_or_404(UserProfile, user=user)

        # All tags
        tags_qs = Tags.objects.all()

        # Creating post
        post = Post.objects.create(title=title, post_content=post_content, author=user)

        selected_tags = []
        flag = True
        for tag in tags_qs:
            # Adding tags to post
            if str(tag) in tags_str:
                # Checking if tag is present in appended string of tags.
                post.tags.add(tag)
                selected_tags.append(str(tag))
                flag = False

        if flag:
            # If no tag selected, by default 'other' tag is added.
            tag = Tags.objects.get(name='Other')
            post.tags.add(tag)
            selected_tags.append(str(tag))

        post.save()

        admin = User.objects.get(username="admin")

        # URLs of view
        post_url = reverse("post_detail", kwargs={'slug': post.slug})
        profile_url = reverse("User Profile", kwargs={'username': post.author.username})
        avatar_url = user_profile.avatar.url

        result = "ERR"

        if is_scheduled == 'true':
            if user.is_superuser:
                post.is_scheduled = True
                post.draft = True
                post.save()

                # Sending mail to In charge faculty for permission.
                subject = 'Requesting permission for CC Club Event'

                # Domain of link
                domain = Site.objects.filter()
                email_context = {
                    'title': post.title,
                    'slug': post.slug,
                    'domain': domain.first(),
                }
                html_message = render_to_string('user_profile/mail_template_permission.html', context=email_context)
                plain_message = strip_tags(html_message)
                from_email = "noreply@ccwebsite"

                # Faculties to which email is to be sent
                faculties = User.objects.filter(groups__name='Teacher')
                to = []
                for faculty in faculties:
                    to.append(faculty.email)
                try:
                    mail.send_mail(subject, plain_message, from_email, to, html_message=html_message)
                except mail.BadHeaderError:
                    messages.info(request, f"Invalid Header found, mail not sent!")

                # Teacher group - Used to send notification in one go.
                teachers_group = Group.objects.get(name='Teacher')
                # notify.send(
                #         # Sending notification to all teachers.
                #         user_profile,
                #         recipient=teachers_group,
                #         verb='requested permission for an event.',
                #         target=post,
                #         dp_url=user_profile.avatar.url,
                #         prof_url=reverse("User Profile", kwargs={'username': user.username}),
                #         post_url=post_url,
                #         actor_name=user_profile.user.first_name,
                #         timestamp_=timesince(timezone.now()),
                # )
                result = "ISCH"
            else:
                messages.error(request, f"You are not authenticated for this request.")

        # If post is draft
        elif is_draft == 'true':
            post.draft = True
            post.save()
            result = "DR"
        else:
            # Normal post
            # Notifications
            if post.author.is_superuser:
                result = "SSS"
                # Self verified here only.
                post.verify_status = 1
                post.save()
            else:
                result = "SS"
                # notify.send(
                #         user_profile,
                #         recipient=admin,
                #         verb='requested approval to post.',
                #         target=post,
                #         dp_url=user_profile.avatar.url,
                #         prof_url=reverse("User Profile", kwargs={'username': user.username}),
                #         post_url=post_url,
                #         actor_name=user_profile.user.first_name,
                #         timestamp_=timesince(timezone.now()),
                # )
        """
            Response Acronyms:
            SSS - Normal post by Superuser (Success)
            SS - Normal post (Success)
            DR - Draft
            ISCH - Scheduled post
            ERR - Error
        """
        response_data = {
            'result': result,
            'postTitle': post.title,
            'postUrl': post_url,
            'profileUrl': profile_url,
            'avatarUrl': avatar_url,
            'author': post.author.username,
            'verifyStatus': post.verify_status,
        }

        return JsonResponse(response_data)

        # Tried earlier:
        # likes = post.likes.count()
        # if likes > 1:
        #     likes_count = str(likes) + ' Like'
        # else:
        #     likes_count = str(likes) + 'Likes'
        # if user_profile.avatar:
        #     avatar_url = user_profile.avatar.url
        # else:
        #     avatar_url = '/static/default-profile-picture.jpg'
        # add_comment_url = reverse(add_comment, kwargs={'post_id': post.pk})
        # like_url = reverse('like_toggle', kwargs={'slug': post.slug})
        # response_data = {
        #     'result': 'Post added successfully!',
        # 'postPk': post.pk,
        # 'postTitle': post.title,
        # 'postContent': post.post_content,
        # 'created': timesince(post.published),
        # 'author': post.author.username,
        # 'selectedTags':  selected_tags,
        # 'avatarURL': avatar_url,
        # 'likes': likes,
        # 'likesCountStr': likes_count,
        # 'addCommentURL': add_comment_url,
        # 'isPinned': post.is_pinned,
        # 'likeURL': like_url,
        # }


@login_required
def ajax_del_post(request):
    """
            Function to delete post using AJAX.
    """
    if request.method == "GET":

        # From which page the request is coming(home OR user profile)
        coming_from = request.GET['coming_from']
        post_pk = request.GET['post_pk']
        post_qs = Post.objects.filter(pk=post_pk)

        if post_qs is None:
            # Post does not exist
            result = "ERR"
        else:
            post = post_qs.first()
            post.delete()
            result = "SS"

        response_data = {
            'postPK': post_pk,
            'comingFrom': coming_from,
            'result': result,
        }
        return JsonResponse(response_data)
    else:
        return HttpResponseRedirect(reverse("Index"))


@login_required
def ajax_edit_post(request):
    """
        Function to edit post using AJAX.
    """
    if request.method == "POST":
        pk = request.POST['pk']
        # Updated data
        updated_title = request.POST['title']
        tags_str = request.POST['tags']
        updated_content = request.POST['post_content']
        is_draft = request.POST['is_draft']

        # Fetching original post and all tags
        original_post_qs = Post.objects.filter(pk=pk)
        tags_qs = Tags.objects.all()

        selected_tags = []

        # Setting edited time = Current time
        updated =timezone.now()
        post_url = None
        if original_post_qs is None:
            # Post not found
            result = 'ERR'
            like_url = None
        else:
            original_post = original_post_qs.first()
            original_tags_qs = original_post.tags.all()

            for original_tag in original_tags_qs:
                original_post.tags.remove(original_tag)

            for tag in tags_qs:
                # Adding new tags
                if str(tag) in tags_str:
                    original_post.tags.add(tag)
                    selected_tags.append(str(tag))

            # Updating
            original_post.title = updated_title
            original_post.post_content = updated_content
            original_post.updated = timezone.now()
            updated = original_post.updated
            print("I AM here!")
            if (original_post.verify_status is -1) and (is_draft == 'false'):
                # Undrafting happening
                original_post.draft = False
                print("I was here!")
                admin = User.objects.get(username="admin")
                user_profile = UserProfile.objects.get(user=request.user)
                post_url = reverse("post_detail", kwargs={'slug': original_post.slug}),
                if original_post.author.is_superuser:
                    original_post.draft = False
                    original_post.verify_status = 1
                    original_post.save()
                    result = 'SUD'
                else:
                    # notify.send(
                    #     user_profile,
                    #     recipient=admin,
                    #     verb='requested approval to post.',
                    #     target=original_post,
                    #     dp_url=user_profile.avatar.url,
                    #     prof_url=reverse("User Profile", kwargs={'username': request.user.username}),
                    #     post_url=post_url,
                    #     actor_name=user_profile.user.first_name,
                    #     timestamp_=timesince(timezone.now()),
                    # )
                    result = 'UD'
            else:
                result = "SS"

            """
                Acronyms - 
                SUD - Superuser Undrafting
                UD - Normal Undrafting
                SS - Normal edit success
            """

            original_post.save()

            like_url = reverse('like_toggle', kwargs={'slug': original_post.slug})

        response_data = {
            'result': result,
            'title': updated_title,
            'content': updated_content,
            'selectedTags': selected_tags,
            'postPK': pk,
            'updated': timesince(updated),
            'likeUrl': like_url,
            'postUrl': post_url,
        }

        return JsonResponse(response_data)


@login_required
def post_like_toggle(request, slug):
    """
        Function to like/unlike posts using AJAX.
    """

    print("\n\n\n\nLIKE############UNLIKED\n\n\n\n")

    post_qs = Post.objects.filter(slug=slug)
    user = request.user
    count = -1
    pk = -1
    if post_qs is None:
        # Post does not exist
        result = "ERR"

    else:
        # Post exists
        post = post_qs.first()
        pk = post.pk
        if user.is_authenticated:
            if user in post.likes.all():
                # Like removed
                post.likes.remove(user)
                result = "UNLIKED"
            else:
                # Like Added
                post.likes.add(user)
                result = "LIKED"
                user_profile = get_object_or_404(UserProfile, user=user)

                # Post author is not same as user liking the post
                if str(user_profile.user) != str(post.author):
                    # Notification sent to post author
                    # notify.send(
                    #     user_profile,
                    #     recipient=post.author,
                    #     verb='liked your post.',
                    #     target=post,
                    #     dp_url=user_profile.avatar.url,
                    #     prof_url=reverse("User Profile", kwargs={'username': user.username}),
                    #     post_url=reverse("post_detail", kwargs={'slug': post.slug}),
                    #     actor_name=user_profile.user.first_name,
                    #     timestamp_=timesince(timezone.now()),
                    # )

                    channel_layer = get_channel_layer()

                    verb = "liked your post"
                    event = "Liked"

                    text_dict = {
                        "event": event,
                        'recipient_username': post.author.username,
                        'sender_username': user.username,
                        'sender_name': user.first_name,
                        'post_pk': post.pk,
                        'verb': verb,
                        'data': {
                            'post_title': post.title,
                            'dp_url': user_profile.avatar.url,
                            'prof_url': reverse("User Profile", kwargs={'username': user.username}),
                            'post_url': reverse("post_detail", kwargs={'slug': post.slug}),
                        }
                    }

                    async_to_sync(channel_layer.group_send)(
                        "like_notif", {
                            "type": "notif_like",
                            "text": json.dumps(text_dict),
                        }
                    )

            count = post.likes.count()
        else:
            result = "UNA"
    """
        Response Acronyms:
            ERR - Error
            UNLIKED - Unliked
            LIKED - Liked
            UNA - User not authenticated
    """

    response_data = {
        'result': result,
        'likesCount': count,
        'postPK': pk,
    }

    return JsonResponse(response_data)


def post_detail(request, slug):
    """
        This function renders Post Detail View.
    """

    # check_profile = None
    # flag = False
    #
    # if request.user.is_authenticated:
    #     check_profile = get_object_or_404(UserProfile, user=request.user)
    #     flag = set_profile(request, request.user)
    #     check_profile = get_object_or_404(UserProfile, user=request.user)
    #
    # if check_profile is not None:
    #     if not check_profile.is_profile_set:
    #         messages.info(request, f"User profile not set")
    #         return HttpResponseRedirect(reverse('Index'))

    # Fetching post(using slug), post author, user profile of author
    # all user profiles, all comments and all tags.
    post_qs = Post.objects.filter(slug=slug)
    if post_qs:
        post = post_qs.first()
        post_views = PostView.objects.filter(post=post)
    else:
        messages.info(request, f"This post does not exist.")
        return HttpResponseRedirect(reverse('User Profile', kwargs={'username': request.user.username}))
    author = post.author
    author_profile = get_object_or_404(UserProfile, user=author)
    user_profiles = UserProfile.objects.all()
    comments = Comment.objects.all()
    tags = Tags.objects.all()

    # Comment adding form and user signup form
    comment_form = CommentForm()
    form = UserSignupForm()

    context = {
        'post': post,
        'author': author,
        'author_profile': author_profile,
        'comments': comments,
        'comment_form': comment_form,
        'user_profiles': user_profiles,
        'tags': tags,
        'form': form,
        'post_views': post_views,
    }

    faculties = User.objects.filter(groups__name='Teacher')
    # print("Iwas out of everything")
    if post.draft:
        # print("I was in drafts.")
        if post.is_scheduled:
            # print("Iwas in is scheduled")
            # If post is scheduled and draft, only admin and teachers can see it
            if (request.user in faculties) or (request.user.username == 'admin'):
                return render(request, 'post/post_detail.html', context)
            else:
                messages.info(request, f"Sorry, You can't see this yet.")
                return HttpResponseRedirect(reverse('Index'))
        elif post.author != request.user:
            # If someone tries to access Drafts of others through URL.
            messages.info(request, f"Sorry, You can't see this yet.")
            return HttpResponseRedirect(reverse('Index'))

    return render(request, 'post/post_detail.html', context)


@login_required
def approve_post(request, slug):
    """
        This function approves the post to be posted among public.
    """
    if request.user.is_superuser:
        post_qs = Post.objects.filter(slug=slug)
        # Checking if post exists
        if post_qs:
            post = post_qs.first()
            author = post.author
            author_profile = UserProfile.objects.get(user=author)
            # Checking if Post is not yet verified by Admin
            if post.verify_status == -1:
                # Verify it
                """
                    Status code -
                    -1 : Not verified/rejected yet.
                     0 : Rejected
                     1 : Approved
                """
                post.verify_status = 1
                post.save()
                admin_prof = get_object_or_404(UserProfile, user=request.user)
                if post.author != request.user:
                    # Admin wont send notification to itself.
                    # notify.send(
                    #     # Sending notification to post author
                    #     admin_prof,
                    #     recipient=author,
                    #     verb='approved this post.',
                    #     target=post,
                    #     dp_url=admin_prof.avatar.url,
                    #     prof_url=reverse("User Profile", kwargs={'username': admin_prof.user.username}),
                    #     post_url=reverse("post_detail", kwargs={'slug': post.slug}),
                    #     actor_name=admin_prof.user.first_name,
                    #     timestamp_=timesince(timezone.now()),
                    # )
                    messages.success(request, f"You have approved a post.")

                    # For Email
                    if author_profile.is_subscribed:

                        subject = "Post approved by admin."
                        domain = Site.objects.filter()
                        email_context = {
                            'domain': domain,
                            'status': 'approved',
                            'post': post,
                        }
                        html_message = render_to_string('user_profile/mail_template_post_approval.html', context=email_context)
                        plain_message = strip_tags(html_message)
                        from_email = "noreply@ccwebsite"
                        to = str(author.email)
                        try:
                            mail.send_mail(subject, plain_message, from_email, [to], html_message=html_message)
                        except mail.BadHeaderError:
                            messages.info(request, f"Invalid Header found, mail not sent!")

            else:
                messages.error(request, f"Oops! Something went wrong. Try again!")
        else:
            messages.error(request, f"Oops! Something went wrong. Try again!")

        return HttpResponseRedirect(reverse("User Profile", kwargs={'username': request.user.username}))
    else:
        messages.info(request, f"You are not authorised to complete this action!")
    return HttpResponseRedirect(reverse("Index"))


@login_required
def reject_post(request, slug):
    """
        This function rejects the post to be posted among public.
    """
    if request.user.is_superuser:
        post_qs = Post.objects.filter(slug=slug)
        # Checking if post exists
        if post_qs:
            post = post_qs.first()
            author = post.author
            author_profile = UserProfile.objects.get(user=author)
            # Checking if Post is not yet verified by Admin
            if post.verify_status == -1:
                # Reject it.
                """
                    Status code -
                    -1 : Not verified/rejected yet.
                     0 : Rejected
                     1 : Approved
                """
                post.verify_status = 0
                post.save()
                admin_prof = get_object_or_404(UserProfile, user=request.user)
                if post.author != request.user:
                    # notify.send(
                    #     # Send notification to post author.
                    #     admin_prof,
                    #     recipient=author,
                    #     verb='rejected this post.',
                    #     target=post,
                    #     dp_url=admin_prof.avatar.url,
                    #     prof_url=reverse("User Profile", kwargs={'username': admin_prof.user.username}),
                    #     post_url=reverse("post_detail", kwargs={'slug': post.slug}),
                    #     actor_name=admin_prof.user.first_name,
                    #     timestamp_=timesince(timezone.now()),
                    # )
                    messages.success(request, f"You have rejected a post.")

                    # For Email
                    if author_profile.is_subscribed:

                        subject = "Post rejected by admin."
                        domain = Site.objects.filter()
                        email_context = {
                            'domain': domain,
                            'status': 'rejected',
                            'post': post,
                        }
                        html_message = render_to_string('user_profile/mail_template_post_approval.html', context=email_context)
                        plain_message = strip_tags(html_message)
                        from_email = "noreply@ccwebsite"
                        to = str(author.email)
                        try:
                            mail.send_mail(subject, plain_message, from_email, [to], html_message=html_message)
                        except mail.BadHeaderError:
                            messages.info(request, f"Invalid Header found, mail not sent!")
            else:
                messages.error(request, f"Oops! Something went wrong. Try again!")
        else:
            messages.error(request, f"Oops! Something went wrong. Try again!")

        return HttpResponseRedirect(reverse("User Profile", kwargs={'username': request.user.username}))
    else:
        messages.info(request, f"You are not authorised to complete this action!")
    return HttpResponseRedirect(reverse("Index"))


@login_required
def edit_comment(request, pk):
    """
        A function to edit comments.
    """
    if request.method == "POST":
        updated_comment = request.POST['updated_comment']
        comment = Comment.objects.get(pk=pk)
        comment.comment_text = updated_comment
        comment.save()
        result = "SS"
        response = {
            'result': result
        }
        return JsonResponse(response)


@login_required
def delete_comment(request, pk):
    """
        A function to delete comments.
    """
    comment_qs = Comment.objects.filter(pk=pk)
    post = None
    # Checking if comment exists
    if comment_qs:
        # Comment deleted
        comment = comment_qs.first()
        post = comment.post
        comment.delete()
        messages.success(request, f"Comment deleted successfully.")
    else:
        # Comment does not exist
        messages.info(request, f"This comment does not exist.")
    return HttpResponseRedirect(reverse('post_detail', kwargs={'slug': post.slug}))


def record_view(request, post_id):
    """
        This function count number of hits/views on a post.
    """
    post = get_object_or_404(Post, pk=post_id)
    if not PostView.objects.filter(post=post, user=request.user, session=request.session.session_key):
        view = PostView(
            post=post,
            # To fetch IP Address
            ip=request.META['REMOTE_ADDR'],
            user=request.user,
            created=timezone.now(),
            session=request.session.session_key
        )
        view.save()
    count = PostView.objects.filter(post=post).count()
    post.unique_view_no = count
    post.save()
    profile = UserProfile.objects.get(user=request.user)
    # return HttpResponse(u"%s" % PostView.objects.filter(post=post).count())
    result = "SS"
    response = {
        'result': result,
        'title': post.title,
        'count': count,
        'profileURL': reverse('User Profile', kwargs={'username': request.user.username }),
        'avatarURL': profile.avatar.url,
        'username': request.user.username,
        'firstName': request.user.first_name,
        'lastName': request.user.last_name,
    }
    return JsonResponse(response)

# Tried Earlier:

# from rest_framework.views import APIView
# from rest_framework.response import Response
# from rest_framework import authentication, permissions
# from django.contrib.auth.models import User
#
#
# class PostLikeAPIToggle(APIView):
#
#     authentication_classes = [authentication.SessionAuthentication, ]
#     permission_classes = [permissions.IsAuthenticated, ]
#
#     def get(self, request, slug=None, format=None):
#         # slug = self.kwargs.get('slug')
#         obj = get_object_or_404(Post, slug=slug)
#         # url_ = HOME + '#like-' + str(obj.pk)
#         user = self.request.user
#         updated = False
#         liked = False
#         if user.is_authenticated:
#             if user in obj.likes.all():
#                 liked = False
#                 obj.likes.remove(user)
#             else:
#                 liked = True
#                 obj.likes.add(user)
#             updated = True
#         count = obj.likes.count()
#         data = {
#             'updated': updated,
#             'liked': liked,
#             'likescount': count,
#         }
#         return Response(data)

# @login_required
# def add_post(request):
#     tags = Tags.objects.all()
#     if request.method == 'POST':
#         addpostform = PostForm(request.POST)
#         if addpostform.is_valid():
#             post = addpostform.save(commit=False)  # Why commit=False?
#             post.save()
#             post.author = request.user
#             raw_tags = addpostform.cleaned_data.get('tags')
#
#             for raw_tag in raw_tags:
#                 if raw_tag in tags:
#                     post.tags.add(raw_tag)
#             post.save()
#             messages.success(request, f"Success! Check Pending Posts in your profile!")
#             return HttpResponseRedirect(reverse("Index"))
#     else:
#         addpostform = PostForm()
#     form = UserSignupForm()
#     posts = page_maker(request, Post)
#     comment_form = CommentForm()
#     context = {
#         'form': form,
#         'addpostform': addpostform,
#         'posts': posts,
#         'tags': tags,
#         'comment_form': comment_form,
#     }
#     return render(request, 'home/index.html', context)