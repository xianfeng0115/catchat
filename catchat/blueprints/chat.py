# -*- coding: utf-8 -*-
"""
    :author: Grey Li (李辉)
    :url: http://greyli.com
    :copyright: © 2018 Grey Li <withlihui@gmail.com>
    :license: MIT, see LICENSE for more details.
"""
from flask import render_template, redirect, url_for, request, Blueprint, current_app, abort,flash
from flask_login import current_user, login_required
from flask_socketio import emit
import socket,binascii,threading

from catchat.extensions import socketio, db
from catchat.forms import ProfileForm
from catchat.models import Message, User
from catchat.utils import to_html, flash_errors

chat_bp = Blueprint('chat', __name__)
chat_bp.debug = True

online_users = []

# 服务端接收消息并且广播消息
@socketio.on('new message')
def new_message(message_body):
    # 将HTML传过来的格式数据包转为Python格式
    # html_message = to_html(message_body)
    html_message = '测试数据'
    # 将数据包存储在数据库
    print(current_user)
    message = Message(author=current_user._get_current_object(), body=html_message)
    db.session.add(message)
    db.session.commit()
    # 发送数据包,message作为参数传入
    emit('new message',
         {'message_html': render_template('chat/_message.html', message=message),
          'message_body': html_message,
          'gravatar': current_user.gravatar,
          'nickname': current_user.nickname,
          'user_id': current_user.id},
         broadcast=True)

# 推送函数
def test():
    for i in range(10):
        data = '服务端发来的测试数据'
        message = Message(author=current_user._get_current_object(), body=data)
        emit('new message',
             {'message_html': render_template('chat/_message.html', message=message),
              'message_body': data,
              'gravatar': current_user.gravatar,
              'nickname': current_user.nickname,
              'user_id': current_user.id
              },
             broadcast=True)

# 希望点击promote按钮后，服务端会推送10包数据到客户端，为了防止卡顿加了个线程
@chat_bp.route('/promote')
def promote():
    t = threading.Thread(target=test)
    t.setDaemon(True)
    t.start()

    amount = current_app.config['CATCHAT_MESSAGE_PER_PAGE']
    messages = Message.query.order_by(Message.timestamp.asc())[-amount:]
    user_amount = User.query.count()
    return render_template('chat/home.html', messages=messages, user_amount=user_amount)

@socketio.on('connect')
def connect():
    global online_users
    if current_user.is_authenticated and current_user.id not in online_users:
        online_users.append(current_user.id)
    emit('user count', {'count': len(online_users)}, broadcast=True)

@socketio.on('disconnect')
def disconnect():
    global online_users
    if current_user.is_authenticated and current_user.id in online_users:
        online_users.remove(current_user.id)
    emit('user count', {'count': len(online_users)}, broadcast=True)

@chat_bp.route('/')
def home():
    amount = current_app.config['CATCHAT_MESSAGE_PER_PAGE']
    messages = Message.query.order_by(Message.timestamp.asc())[-amount:]
    user_amount = User.query.count()
    return render_template('chat/home.html', messages=messages, user_amount=user_amount)

@chat_bp.route('/messages')
def get_messages():
    page = request.args.get('page', 1, type=int)
    pagination = Message.query.order_by(Message.timestamp.desc()).paginate(
        page, per_page=current_app.config['CATCHAT_MESSAGE_PER_PAGE'])
    messages = pagination.items
    return render_template('chat/_messages.html', messages=messages[::-1])


@chat_bp.route('/profile', methods=['GET', 'POST'])
@login_required
def profile():
    form = ProfileForm()
    if form.validate_on_submit():
        current_user.nickname = form.nickname.data
        current_user.github = form.github.data
        current_user.website = form.website.data
        current_user.bio = form.bio.data
        db.session.commit()
        return redirect(url_for('.home'))
    flash_errors(form)
    return render_template('chat/profile.html', form=form)


@chat_bp.route('/profile/<user_id>')
def get_profile(user_id):
    user = User.query.get_or_404(user_id)
    return render_template('chat/_profile_card.html', user=user)


@chat_bp.route('/message/delete/<message_id>', methods=['DELETE'])
def delete_message(message_id):
    message = Message.query.get_or_404(message_id)
    if current_user != message.author and not current_user.is_admin:
        abort(403)
    db.session.delete(message)
    db.session.commit()
    return '', 204
