from django.shortcuts import render, redirect, reverse
from django.http import JsonResponse
# from django.contrib.contenttypes.models import ContentType
from django.contrib import messages
from post import views as post_view
from django.utils.timesince import timesince
from django.utils import timezone

# Imported Models
from post.models import Post, Tags
from user_profile.models import UserProfile
from .models import Comment

# Imported Forms
from .forms import CommentForm
from home.forms import UserSignupForm
from post.forms import PostForm

# 3rd Party imports
# from notifications.signals import notify
# Create your views here.

HOME = '/'


def add_comment(request, post_id):
    """
        Function to add comments.
        Currently NOT IN USE.
    """
    post = Post.objects.get(id=post_id)

    if request.method == 'POST':
        comment_form = CommentForm(request.POST)
        if comment_form.is_valid():

            # Content of comment
            content_data = comment_form.cleaned_data.get('comment_text')

            parent_obj = None

            try:
                # If parent exists
                parent_id = int(request.POST['parent_id'])
            except:
                # If parent doesn't exist
                parent_id = None

            # Check if parent_id exists
            if parent_id:
                parent_qs = Comment.objects.filter(id=parent_id)

                # Check if parent_qs is not NULL
                if parent_qs.exists() and parent_qs.count() == 1:
                    parent_obj = parent_qs.first()

            # Create new comment
            new_comment, created = Comment.objects.get_or_create(
                user=request.user,
                post=post,
                comment_text=content_data,
                parent=parent_obj,
            )

            if created:

                # Send success message
                messages.success(request, f'Comment posted!')
                if parent_obj is None:
                    return redirect(HOME + '#comment-' + str(post.pk) + '-' + str(new_comment.pk))
                else:
                    return redirect(HOME + '#comment-' + str(post.pk) + '-' + str(parent_obj.pk))
                # return HttpResponseRedirect(new_comment.comment_text.get_absolute_url())
            else:
                messages.error(request, f"Not created!")
                return redirect(HOME)
        # else:
            # messages.error(request, f"Please write some comment!")
            # return redirect(HOME)
    else:
        comment_form = CommentForm()
    form = UserSignupForm()
    add_post_form = PostForm()
    posts = post_view.page_maker(request, Post)
    user_profiles = UserProfile.objects.all()
    tags = Tags.objects.all()
    comments = Comment.objects.all()
    context = {
        'comment_form': comment_form,
        'form': form,
        'addpostform': add_post_form,
        'posts': posts,
        'tags': tags,
        'user_profiles': user_profiles,
        'comments': comments,
    }
    return render(request, 'home/index.html', context)

    # Tried earlier:
    # initial_data = {
    #     'content_type': post.get_content_type,
    #     'object_id': post.id,
    #
    # }
    # c_type = form.cleaned_data.get('content_type')
    # content_type = ContentType.objects.get(model=c_type)
    # obj_id = form.cleaned_data.get('object_id')
    # content_data = form.cleaned_data.get('content')
    # new_comment, created = Comment.objects.get_or_create(
    #     user=request.user,
    #     content_type=content_type,
    #     object_id=obj_id,
    #     content=content_data,
    # )


def ajax_add_comment(request, post_id):
    """
        Function to add comments through AJAX.
        Currently IN USE.
    """
    if request.method == "POST":
        post_pk = request.POST['post_pk']
        parent_pk = request.POST['comment_pk']
        comment_content = request.POST['comment_content']
        # comment_content = comment_content.strip()
        # print(comment_content)
        parent = None
        post = None
        parent_qs = Comment.objects.filter(pk=parent_pk)
        post_qs = Post.objects.filter(pk=post_pk)

        # Check if parent comment exists
        if parent_qs is not None:
            parent = parent_qs.first()

        # Check if post exists
        if post_qs is not None:
            post = post_qs.first()

        # Create comment
        new_comment, created = Comment.objects.get_or_create(
            user=request.user,
            post=post,
            comment_text=comment_content,
            parent=parent,
        )

        user_profile = UserProfile.objects.get(user=request.user)
        if user_profile.avatar:
            # URL of profile picture
            avatar_url = user_profile.avatar.url

        # Time at which comment is created
        timestamp = new_comment.timestamp

        # Count of children comment
        children_count = new_comment.children().count()

        if children_count == 1:
            count_str = str(children_count) + " Reply |"
        else:
            count_str = str(children_count) + " Replies |"

        # Sending notifications
        if created:
            # Check if comment is NOT a reply to other comment.
            if parent is None:
                # Check if comment author and post author are NOT same.
                if str(user_profile.user) != str(post.author):
                    pass
                    # notify.send(
                    #     user_profile,
                    #     recipient=post.author,
                    #     verb='commented on your post.',
                    #     target=post,
                    #     dp_url=user_profile.avatar.url,
                    #     prof_url=reverse("User Profile", kwargs={'username': user_profile.user.username}),
                    #     post_url=reverse("post_detail", kwargs={'slug': post.slug}),
                    #     actor_name=user_profile.user.first_name,
                    #     timestamp_=timesince(timezone.now()),
                    # )
            else:
                # This comment is reply to some other comment.
                # Check if comment author and post author are NOT same.
                if str(user_profile.user) != str(post.author):
                    pass
                    # Send notification to post author.
                    # notify.send(
                    #     user_profile,
                    #     recipient=post.author,
                    #     verb='replied to a comment.',
                    #     target=post,
                    #     dp_url=user_profile.avatar.url,
                    #     prof_url=reverse("User Profile", kwargs={'username': user_profile.user.username}),
                    #     post_url=reverse("post_detail", kwargs={'slug': post.slug}),
                    #     actor_name=user_profile.user.first_name,
                    #     timestamp_=timesince(timezone.now()),
                    # )

                # Check if parent comment author and post author are NOT same.
                if str(parent.user) != str(user_profile.user):
                    pass
                    # Send notification to Parent comment author
                    # notify.send(
                    #     user_profile,
                    #     recipient=parent.user,
                    #     verb='replied to your comment.',
                    #     target=post,
                    #     dp_url=user_profile.avatar.url,
                    #     prof_url=reverse("User Profile", kwargs={'username': user_profile.user.username}),
                    #     post_url=reverse("post_detail", kwargs={'slug': post.slug}),
                    #     actor_name=user_profile.user.first_name,
                    #     timestamp_=timesince(timezone.now()),
                    # )
        # Sending notifications ended

        # Other URL's
        add_comment_url = reverse('Add Comment', kwargs={'post_id': post_pk})
        user_profile_url = reverse('User Profile', kwargs={'username': request.user.username})

        if created:
            result = "SS"
        else:
            result = "ERR"

        """
            Acronyms:
            SS: Success
            ERR: Error
        """

        response_data = {
            'result': result,
            'avatarURL': avatar_url,
            'userName': request.user.username,
            'timestamp': timesince(timestamp),
            'countStr': count_str,
            'addCommentURL': add_comment_url,
            'userProfileURL': user_profile_url,
            # 'commentCount': comment_count,
            # 'replyCount': reply_count,
        }

        return JsonResponse(response_data)

        # Tried earlier:
        # comments = Comment.objects.filter(post=post)
        # comment_count = comments.count()
        # replies = Comment.objects.filter(post=post).filter(parent=parent)
        # reply_count = replies.count()
