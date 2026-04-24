from flask import Blueprint, jsonify, request
from threaddit import db
from threaddit.reactions.models import Reactions
from threaddit.posts.models import PostInfo
from threaddit.comments.models import CommentInfo
from threaddit.cache import (
    set_post_vote_count,
    increment_post_vote_count,
    set_comment_vote_count,
    increment_comment_vote_count,
    set_user_vote,
    delete_user_vote,
    get_user_votes,
)
from flask_login import current_user, login_required

reactions = Blueprint("reactions", __name__, url_prefix="/api")


def calculate_vote_delta(old_vote, new_vote):
    if old_vote is None and new_vote is not None:
        return 1 if new_vote else -1
    elif old_vote is not None and new_vote is None:
        return -1 if old_vote else 1
    elif old_vote is not None and new_vote is not None and old_vote != new_vote:
        return 2 if new_vote else -2
    return 0


def update_vote_count_in_cache(content_type, content_id, delta):
    if content_type == "post":
        increment_post_vote_count(content_id, delta)
    elif content_type == "comment":
        increment_comment_vote_count(content_id, delta)


def get_current_vote_from_db(content_type, content_id):
    if content_type == "post":
        return Reactions.query.filter_by(post_id=content_id, user_id=current_user.id).first()
    elif content_type == "comment":
        return Reactions.query.filter_by(comment_id=content_id, user_id=current_user.id).first()
    return None


def get_post_karma_from_db(post_id):
    post_info = PostInfo.query.filter_by(post_id=post_id).first()
    return post_info.post_karma if post_info else 0


def get_comment_karma_from_db(comment_id):
    comment_info = CommentInfo.query.filter_by(comment_id=comment_id).first()
    return comment_info.comment_karma if comment_info else 0


@reactions.route("/reactions/post/<post_id>", methods=["PUT"])
@login_required
def add_reaction_post(post_id):
    return handle_vote("post", post_id)


@reactions.route("/reactions/post/<post_id>", methods=["PATCH"])
@login_required
def update_reaction_post(post_id):
    return handle_vote("post", post_id)


@reactions.route("/reactions/post/<post_id>", methods=["DELETE"])
@login_required
def delete_reaction_post(post_id):
    return handle_vote("post", post_id, is_delete=True)


@reactions.route("/reactions/comment/<comment_id>", methods=["PUT"])
@login_required
def add_reaction_comment(comment_id):
    return handle_vote("comment", comment_id)


@reactions.route("/reactions/comment/<comment_id>", methods=["PATCH"])
@login_required
def update_reaction_comment(comment_id):
    return handle_vote("comment", comment_id)


@reactions.route("/reactions/comment/<comment_id>", methods=["DELETE"])
@login_required
def delete_reaction_comment(comment_id):
    return handle_vote("comment", comment_id, is_delete=True)


def handle_vote(content_type, content_id, is_delete=False):
    try:
        if is_delete:
            new_vote = None
        else:
            if not request.json or "is_upvote" not in request.json:
                return jsonify({"message": "Invalid Reaction"}), 400
            new_vote = request.json.get("is_upvote")

        existing_reaction = get_current_vote_from_db(content_type, content_id)
        old_vote = existing_reaction.is_upvote if existing_reaction else None

        if old_vote == new_vote:
            return jsonify({
                "message": "Vote unchanged",
                "current_vote": old_vote,
            }), 200

        delta = calculate_vote_delta(old_vote, new_vote)

        db.session.begin_nested()

        if new_vote is None:
            if existing_reaction:
                Reactions.query.filter_by(
                    **{f"{content_type}_id": content_id},
                    user_id=current_user.id
                ).delete()
                delete_user_vote(current_user.id, content_type, content_id)
        elif existing_reaction:
            existing_reaction.is_upvote = new_vote
            set_user_vote(current_user.id, content_type, content_id, new_vote)
        else:
            new_reaction = Reactions(
                user_id=current_user.id,
                is_upvote=new_vote,
                **{f"{content_type}_id": content_id}
            )
            db.session.add(new_reaction)
            set_user_vote(current_user.id, content_type, content_id, new_vote)

        db.session.commit()

        update_vote_count_in_cache(content_type, content_id, delta)

        return jsonify({
            "message": "Vote updated successfully",
            "current_vote": new_vote,
            "vote_delta": delta,
        }), 200

    except Exception as e:
        db.session.rollback()
        return jsonify({"message": f"Vote failed: {str(e)}"}), 500


@reactions.route("/reactions/user", methods=["GET"])
@login_required
def get_user_reactions():
    cached_votes = get_user_votes(current_user.id)

    if cached_votes is not None:
        return jsonify({
            "post_votes": cached_votes,
        }), 200

    reactions = Reactions.query.filter_by(user_id=current_user.id).all()

    post_votes = {}
    comment_votes = {}

    for reaction in reactions:
        if reaction.post_id is not None:
            post_votes[reaction.post_id] = reaction.is_upvote
            set_user_vote(current_user.id, "post", reaction.post_id, reaction.is_upvote)
        if reaction.comment_id is not None:
            comment_votes[reaction.comment_id] = reaction.is_upvote
            set_user_vote(current_user.id, "comment", reaction.comment_id, reaction.is_upvote)

    return jsonify({
        "post_votes": post_votes,
        "comment_votes": comment_votes,
    }), 200
