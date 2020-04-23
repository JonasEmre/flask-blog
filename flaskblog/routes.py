import os
import secrets
from PIL import Image
from flask import render_template, url_for, flash, redirect, request, abort
from flaskblog import app, db, bcrypt, mail
from flaskblog.form import (RegistrationForm, LoginForm, UpdateForm, PostForm,
                            RequestResetForm, PasswordResetForm)
from flaskblog.models import User, Post
from flask_login import login_user, current_user, logout_user, login_required
from flask_mail import Message


@app.route("/")
@app.route("/home")
def home():
    page = request.args.get('page', 1, type=int)
    posts = Post.query.order_by(Post.date_posted.desc()) \
        .paginate(page=page, per_page=4)
    return render_template("home.html", posts=posts, title="Ana Sayfa")


@app.route("/about")
def about():
    return render_template("about.html", title="Hakkımda")


@app.route("/register", methods=['GET', 'POST'])
def register():
    if current_user.is_authenticated:
        return redirect(url_for('home'))
    form = RegistrationForm()
    if form.validate_on_submit():
        hash_pw = bcrypt.generate_password_hash(form.password.data).decode('utf-8')
        user = User(username=form.username.data, email=form.email.data, password=hash_pw)
        db.session.add(user)
        db.session.commit()
        flash('Başarılı üyelik', 'success')
        return redirect(url_for('login'))
    return render_template("register.html", title="Üye Ol", form=form)


@app.route("/login", methods=['GET', 'POST'])
def login():
    if current_user.is_authenticated:
        return redirect(url_for('home'))
    form = LoginForm()
    if form.validate_on_submit():
        user = User.query.filter_by(email=form.email.data).first()
        if user and bcrypt.check_password_hash(user.password, form.password.data):
            login_user(user, remember=form.remember.data)
            next_page = request.args.get('next')
            if next_page:
                next_page = next_page[1:]
            return redirect(url_for(next_page)) if next_page else redirect(url_for('home'))
        else:
            flash('Hatalı giriş. E-mail ya da şifrenizi kontrol edin.', 'danger')
    return render_template("login.html", title="Giriş", form=form)


@app.route('/logout')
def log_out():
    logout_user()
    return redirect(url_for('home'))


def save_picture(form_picture):
    random_hex = secrets.token_hex(8)
    f_ext = os.path.splitext(form_picture.filename)[1]
    picture_fn = random_hex + f_ext
    picture_path = os.path.join(app.root_path, 'static\profile_pics', picture_fn)
    output_size = (200, 200)
    i = Image.open(form_picture)
    i.thumbnail(output_size)
    i.save(picture_path)
    return picture_fn


@app.route('/account', methods=['GET', 'POST'])
@login_required
def account():
    form = UpdateForm()
    if form.validate_on_submit():
        if form.file:
            new_image = save_picture(form.file.data)
            current_user.image_file = new_image
            db.session.commit()
        current_user.username = form.username.data
        current_user.email = form.email.data
        db.session.commit()
        flash('Bilgiler güncellendi.', 'success')
        return redirect(url_for('account'))
    elif request.method == 'GET':
        form.username.data = current_user.username
        form.email.data = current_user.email
    image_file = url_for('static', filename='profile_pics/' + current_user.image_file)
    return render_template('account.html', title='Hesabım', image_file=image_file, form=form)


@app.route('/posts/new', methods=['GET', 'POST'])
def new_post():
    form = PostForm()
    if form.validate_on_submit():
        post = Post(title=form.title.data, content=form.content.data,
                    author=current_user)
        db.session.add(post)
        db.session.commit()
        flash('Blog paylaştınız', 'success')
        return redirect(url_for('home'))
    return render_template('new_post.html', title='Yeni Blog',
                           form=form, legend='Yeni Gönderi Oluştur')


@app.route('/posts/<int:post_id>')
def post(post_id):
    post = Post.query.get_or_404(post_id)
    return render_template('post.html', title=post.title, post=post)


@app.route('/posts/<int:post_id>/update', methods=['GET', 'POST'])
@login_required
def update_post(post_id):
    post = Post.query.get_or_404(post_id)
    if post.author != current_user:
        abort(403)
    form = PostForm()
    if form.validate_on_submit():
        post.title = form.title.data
        post.content = form.content.data
        db.session.commit()
        flash('Gönderi başarıyla güncellendi', 'success')
        return redirect(url_for('post', post_id=post_id))
    elif request.method == 'GET':
        form.title.data = post.title
        form.content.data = post.content
    return render_template('new_post.html', title='Gönderi Güncelle',
                           form=form, legend='Gönderi Güncelle')


@app.route('/posts/<int:post_id>/delete', methods=['POST'])
@login_required
def delete_post(post_id):
    post = Post.query.get_or_404(post_id)
    if post.author != current_user:
        abort(403)
    db.session.delete(post)
    db.session.commit()
    flash('Gönderi silindi!', 'success')
    return redirect(url_for('home'))


@app.route('/user/<string:username>')
def user_posts(username):
    page = request.args.get('page', 1, type=int)
    user = User.query.filter_by(username=username).first_or_404()
    posts = Post.query.filter_by(author=user) \
        .order_by(Post.date_posted.desc()) \
        .paginate(page=page, per_page=3)
    return render_template("user_posts.html", posts=posts, title=f"{username}", user=user)


def send_reset_mail(user):
    token = user.get_reset_token()
    msg = Message('Şifre Yenileme Linki', sender='y.emretoktas@gmail.com',
                  recipients=[user.email])
    msg.body = f'''Şifre yenileme için aşağıda gönderilen linke basınız.
    {url_for('reset_password', token=token, _external=True)}

    Eğer bu talebi oluşturmadıysanız görmezden gelebilirsiniz.
        '''
    mail.send(msg)


@app.route('/reset_password', methods=['GET', 'POST'])
def reset_request():
    if current_user.is_authenticated:
        return redirect(url_for('home'))
    form = RequestResetForm()
    if form.validate_on_submit():
        user = User.query.filter_by(email=form.email.data).first()
        send_reset_mail(user)
        flash('Şifre yenileme talebiniz için e-posta adresinize link gönderildi.', 'info')
        return redirect(url_for('login'))
    return render_template('reset_request.html', form=form, legend='Şifre Yenileme')


@app.route('/reset_password/<token>', methods=['GET', 'POST'])
def reset_password(token):
    if current_user.is_authenticated:
        return redirect(url_for('home'))
    user = User.verify_reset_token(token)
    if user is None:
        flash('Böyle bir kullanıcı yok veya talebin süresi bitmiş', 'warning')
        return redirect(url_for('reset_request'))
    form = PasswordResetForm()
    if form.validate_on_submit():
        hash_pw = bcrypt.generate_password_hash(form.password.data).decode('utf-8')
        user.password = hash_pw
        db.session.commit()
        flash('Şifre başarılı bir şekilde değiştirildi', 'success')
        return redirect(url_for('login'))
    return render_template('request_password.html', form=form, legend='Şifre Yenileme')
