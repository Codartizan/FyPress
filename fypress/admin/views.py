# -*- coding: UTF-8 -*-
from flask import Blueprint, session, request, redirect, url_for, render_template, flash, jsonify, make_response
from flask.views import MethodView
from flask.ext.babel import lazy_gettext as gettext
from fypress.user import level_required, login_required, User, UserEditForm, UserAddForm
from fypress.item import FolderForm, Folder, Media
import json

admin = Blueprint('admin', __name__,  url_prefix='/admin')

messages = {
    'updated'   : gettext('Item updated'),
    'added'     : gettext('Item added')
}

@admin.route('/')
@login_required
def root():
    return render_template('admin/index.html', title='Admin')


"""
    Posts
"""
@admin.route('/posts/new')
@level_required(1)
def posts_add():
    folders = Folder.get_all()
    return render_template('admin/posts_new.html', folders=folders, title=gettext('New - Post'))

"""
    Medias
"""
@admin.route('/medias')
@admin.route('/medias/all')
@level_required(1)
def medias():
    medias =  Media.query.get_all(array=True, order='ORDER BY `media_modified` DESC')

    return render_template('admin/medias.html',  medias=medias, title=gettext('Library - Medias'))

@admin.route('/medias/add/web')
@level_required(1)
def medias_web():
    return render_template('admin/medias_web.html',  title=gettext('Add from Web - Medias'))

@admin.route('/medias/add/upload')
@level_required(1)
def medias_upload():
    return render_template('admin/medias_upload.html',  title=gettext('Medias'))


"""
    Folders
"""
@admin.route('/folders', methods=['POST', 'GET'])
@admin.route('/folders/all', methods=['POST', 'GET'])
@level_required(3)
def folders():
    folders = Folder.get_all(True)
    folder  = None

    if request.args.get('edit') and request.args.get('edit') != 1:
        folder = Folder.query.get(request.args.get('edit'))
        form = FolderForm(obj=folder)
        if form.validate_on_submit():
            form.populate_obj(folder)
            folder.modified = 'NOW()'
            folder.update()
            flash(messages['updated']+' ('+str(folder)+')')
            return redirect(url_for('admin.folders'))
    else:
        form = FolderForm()
        if form.validate_on_submit():
            folder = Folder()
            form.populate_obj(folder)
            folder.created = 'NOW()'
            folder.parent  = 1
            Folder.query.add(folder)
            Folder.build_guid()
            flash(messages['added']+' ('+str(folder)+')')
            return redirect(url_for('admin.folders'))

    return render_template('admin/folders.html', folders=folders, folder=folder, title=gettext('Categories'), form=form)


"""
    Users
"""
@admin.route('/users')
@admin.route('/users/all')
@level_required(4)
def users():
    users = User.query.get_all()
    return render_template('admin/users.html', title=gettext('Users'), users=users)

@admin.route('/users/edit', methods=['POST', 'GET'])
@level_required(4)
def users_edit(id_user=None):
    if not id_user:
        id_user = request.args.get('id')

    user = User.query.get(id_user)
    form = UserEditForm(obj=user)

    if form.validate_on_submit():
        form.populate_obj(user)
        User.query.update(user)
        flash(messages['updated']+' ('+str(user)+')')
        return redirect(url_for('admin.users'))

    return render_template('admin/users_edit.html', title=gettext('Edit - User'), user=user, form=form)

@admin.route('/users/new', methods=['POST', 'GET'])
@level_required(4)
def users_new():
    form = UserAddForm(request.form)

    if form.validate_on_submit():
        user = User()
        form.populate_obj(user)
        User.query.add(user)
        flash(messages['added']+' ('+str(user)+')')
        return redirect(url_for('admin.users'))

    return render_template('admin/users_new.html', title=gettext('New - User'),  form=form)

@admin.route('/users/me', methods=['POST', 'GET'])
@login_required
def users_me():
    return users_edit(session.get('user_id'))


"""
    POST
"""
@admin.route('/medias/upload', methods=['POST'])
@level_required(1)
def post_media():
    return Media.upload(request.files['qqfile'], request.form)


@admin.route('/medias/upload/<uuid>', methods=['POST'])
@level_required(1)
def post_media_delete():
    try:
        #handle_delete(uuid)
        return jsonify(success=True), 200
    except Exception, e:
        return jsonify(success=False, error=e.message), 400

"""
    AJAX
"""
@admin.route('/medias/oembed/add', methods=['POST'])
@level_required(1)
def ajax_oembed_add():

    return ''
    
@admin.route('/medias/oembed', methods=['POST'])
@level_required(1)
def ajax_oembed():
    data = request.form.get('data')
    return Media.add_from_web(data)

@admin.route('/folders/update', methods=['POST'])
@level_required(3)
def ajax_folders():
    data = json.loads(request.form.get('data'))
    if data:
        for item in data:
            if item.has_key('id') and item['id'] != '1':
                folder = Folder.query.get(item['id'])
                folder.depth    = item['depth']
                folder.left     = item['left']
                folder.right    = item['right']
                folder.parent = item['parent_id']

                folder.modified = 'NOW()'
                folder.update()
    return ''