# -*- coding: UTF-8 -*-
from flask import jsonify, flash, g, request
from flask.ext.babel import lazy_gettext as gettext
from werkzeug import secure_filename
from BeautifulSoup import *
import hashlib, os, datetime, shutil, magic, json, urllib2

from fypress import app
from fypress.utils import TreeHTML, slugify, url_unique, oembed, FyImage
from fypress.admin.static import messages

import fy_mysql

class Media(fy_mysql.Base):
    # todo allowed {type, icon, }
    allowed_upload_types  = ('image/jpeg', 'image/png', 'image/gif')
    upload_types_images   = ('image/jpeg', 'image/png')

    media_id              = fy_mysql.Column(etype='int', primary_key=True)
    media_hash            = fy_mysql.Column(etype='string', unique=True)
    media_modified        = fy_mysql.Column(etype='datetime')
    media_type            = fy_mysql.Column(etype='string')
    media_guid            = fy_mysql.Column(etype='string', unique=True)
    media_name            = fy_mysql.Column(etype='string')
    media_data            = fy_mysql.Column(etype='json')
    media_icon            = fy_mysql.Column(etype='string')
    media_html            = fy_mysql.Column(etype='string')

    def generate_html(self):
        pass

    def urlify(self, image=False):
        if image:
            try:
                return app.config['UPLOAD_DIRECTORY_URL'] + self.data['var'][image]['guid']
            except:
                return ''
        else:
            return app.config['UPLOAD_DIRECTORY_URL'] + self.guid

    @staticmethod
    def add_from_web(url):
        oembed_ = oembed().get(url) 
        return jsonify(result=oembed_)

    @staticmethod
    def add_oembed(attrs):
        data = json.loads(attrs['data'])
        data['oembed'] =  json.loads(data['oembed'])
        
        now = datetime.datetime.now()
        media_hash          = Media.hash_string(data['url'])

        if Media.query.exist('hash', media_hash):
            media = Media.query.filter(hash=media_hash).one()
            media.modified = 'NOW()'
            Media.query.update(media)
            return jsonify(success=True), 200
        
        media = Media()
        media.hash          = media_hash
        media.modified      = 'NOW()'
        media.type          = 'oembed'
        media.name          = data['title']
        media.guid          = "{}/{}/".format(now.year, now.month)+media_hash
        media.source        = data['url']
        media.icon          = data['fa']
        media.html          = data['html']
        media.data          = {}

        media.data['provider_url'] = data['oembed']['provider_url'].encode('utf8')
        media.data['provider']     = data['oembed']['service']
        if data['oembed'].has_key('author_name'):
            media.data['author_name']  = data['oembed']['author_name']
            media.data['author_url']   = data['oembed']['author_url']
        else:
            media.data['author_name']  = ''
            media.data['author_url']   = ''

        Media.query.add(media)

        if data['oembed'].has_key('thumbnail_url'):
            response = urllib2.urlopen(data['oembed']['thumbnail_url'])
            Media.upload_save(response, os.path.join(Media.upload_path('CHUNKS_DIRECTORY'), media_hash))

            mime = magic.Magic(mime=True)
            mime_file = mime.from_file(os.path.join(Media.upload_path('CHUNKS_DIRECTORY'), media_hash))
            mimes = {'image/jpeg': 'jpg', 'image/jpg': 'jpg', 'image/png':'png'}

            ext         = '.'+mimes[mime_file]
            filename    = 'oembed-'+media_hash+ext
            fdir        = Media.upload_path('UPLOAD_DIRECTORY')
            fpath       = os.path.join(fdir, filename)

            shutil.move(os.path.join(Media.upload_path('CHUNKS_DIRECTORY'), media_hash), fpath)

            images      = FyImage(fpath).generate()
            sizes = {}
            for image in images:
                sizes[image[3]] = {'name': image[1], 'source': os.path.join(Media.upload_path('UPLOAD_DIRECTORY'), image[0]), 'guid': "{}/{}/".format(now.year, now.month)+image[2]}

            media.data['var'] = sizes
            Media.query.update(media)

        flash(messages['added']+' ('+str(media)+')')

        return jsonify(success=True), 200

    @staticmethod
    def upload_path(config):
        now = datetime.datetime.now()
        tmp = "{}/{}".format(now.year, now.month)
        if config == 'CHUNKS_DIRECTORY':
            return os.path.join(app.config[config])
        return os.path.join(app.config[config], tmp)

    @staticmethod
    def upload_save(f, path):
        if not os.path.exists(os.path.dirname(path)):
            os.makedirs(os.path.dirname(path))

        with open(path, 'wb+') as destination:
            destination.write(f.read())

    @staticmethod
    def upload_combine_chunks(total_parts, total_size, source_folder, dest):
        if not os.path.exists(os.path.dirname(dest)):
            os.makedirs(os.path.dirname(dest))

        with open(dest, 'wb+') as destination:
            for i in xrange(int(total_parts)):
                part = os.path.join(source_folder, str(i))
                with open(part, 'rb') as source:
                    destination.write(source.read())
    @staticmethod
    def upload(file, attrs):        
        fhash   = attrs['qquuid']
        upload_type = 'file'
        upload_icon = 'fa-file-o'
        filename = url_unique(secure_filename(attrs['qqfilename']), Media)

        chunked = False

        fdir    = Media.upload_path('UPLOAD_DIRECTORY')
        fpath   = os.path.join(fdir, filename)
        

        if attrs.has_key('qqtotalparts') and int(attrs['qqtotalparts']) > 1:
            chunked = True
            fdir    = Media.upload_path('CHUNKS_DIRECTORY')
            fpath   = os.path.join(fdir, filename, str(attrs['qqpartindex']))

        Media.upload_save(file, fpath)

        if chunked and (int(attrs['qqtotalparts']) - 1 == int(attrs['qqpartindex'])):
            Media.upload_combine_chunks(attrs['qqtotalparts'], attrs['qqtotalfilesize'], os.path.dirname(fpath), os.path.join(Media.upload_path('UPLOAD_DIRECTORY'), filename))
            shutil.rmtree(os.path.dirname(os.path.dirname(fpath)))

        mime = magic.Magic(mime=True)
        mime_file = mime.from_file(os.path.join(Media.upload_path('UPLOAD_DIRECTORY'), filename))

        if mime_file not in Media.allowed_upload_types:
            os.remove(os.path.join(Media.upload_path('UPLOAD_DIRECTORY'), filename))
            return jsonify(success=False, error='File type not allowed.'), 400

        if mime_file in Media.upload_types_images:
             upload_type = 'image'
             upload_icon = ' fa-file-image-o'

        media_hash = Media.hash_file(fpath)
        if Media.query.exist('hash', media_hash):
            media = Media.query.filter(hash=media_hash).one()
            media.modified = 'NOW()'
            Media.query.update(media)

            return jsonify(success=True), 200

        now = datetime.datetime.now()
        media = Media()
        media.hash          = media_hash
        media.modified      = 'NOW()'
        media.type          = upload_type
        media.name          = filename
        media.guid          = "{}/{}/".format(now.year, now.month)+filename
        media.source        = fpath
        media.icon          = upload_icon

        Media.query.add(media)

        if upload_type == 'image':
            images = FyImage(fpath).generate()
            sizes = {}

            for image in images:
                sizes[image[3]] = {'name': image[1], 'source': os.path.join(Media.upload_path('UPLOAD_DIRECTORY'), image[0]), 'guid': "{}/{}/".format(now.year, now.month)+image[2]}

            media.data = {'var':sizes}
            Media.query.update(media)
            
        flash(messages['added']+' ('+str(media)+')')

        return jsonify(success=True), 200

    @staticmethod
    def hash_string(txt):
        hasher = hashlib.sha1()
        hasher.update(txt)
        return hasher.hexdigest() 

    @staticmethod
    def hash_file(file):
        BLOCKSIZE = 65536
        hasher = hashlib.sha1()

        with open(file, 'rb') as afile:
            buf = afile.read(BLOCKSIZE)
            while len(buf) > 0:
                hasher.update(buf)
                buf = afile.read(BLOCKSIZE)

        return hasher.hexdigest()

class Post(fy_mysql.Base):
    post_id               = fy_mysql.Column(etype='int', primary_key=True)
    post_folder_id        = fy_mysql.Column(etype='int') 
    post_user_id          = fy_mysql.Column(etype='int')
    post_parent           = fy_mysql.Column(etype='int')
    post_guid             = fy_mysql.Column(etype='string', unique=True)
    post_modified         = fy_mysql.Column(etype='datetime')
    post_created          = fy_mysql.Column(etype='datetime')
    post_content          = fy_mysql.Column(etype='string')
    post_title            = fy_mysql.Column(etype='string')
    post_excerpt          = fy_mysql.Column(etype='string')
    post_status           = fy_mysql.Column(etype='string', allowed=('publish','draft','pending','trash','revision')) 
    post_comment_status   = fy_mysql.Column(etype='string', allowed=('open', 'close')) 
    post_comment_count    = fy_mysql.Column(etype='int')
    post_slug             = fy_mysql.Column(etype='string', unique=True)
    post_type             = fy_mysql.Column(etype='string')
    post_meta             = fy_mysql.Column(meta=True)

    txt_to_status         = {
        'publish'   : gettext('Public'),
        'draft'     : gettext('Draft'),
        'trash'     : gettext('Deleted'),
        'revision'  : gettext('Revision')
    }

    @property
    def slug(self):
        if self.__dict__.has_key('slug'):
            return self.__dict__['slug']

    @slug.setter
    def slug(self, value):
        self.__dict__['slug'] = slugify(value)

    @staticmethod
    def update(form, post):
        status = 'draft'
        if request.args.get('action') == 'publish':
            status = 'publish'
        if request.args.get('action') == 'draft':
            status = 'draft'

        post.dump()
        post.title          = form['title']
        post.content        = form['content']
        post.folder_id      = form['folder']
        post.modified       = 'NOW()'
        post.status         = status
        post.excerpt        = post.get_excerpt()

        Post.query.update(post)
        post_id = post.id
        post.create_revision()
        
        try:
            limit = Post.query.raw('SELECT post_id FROM fypress_post WHERE post_parent="{}" AND post_status="revision" ORDER BY post_id DESC LIMIT 5,1'.format(post_id)).all()
            Post.query.sql('DELETE FROM _table_ WHERE post_parent="{}" AND post_status="revision"  AND post_id <= {}'.format(post_id, limit[0]['post_id'])).execute()
        except:
            pass

        return post_id

    @staticmethod
    def create(form):
        # Todo: create post, add_revision, update folder count.
        status = 'draft'
        if request.args.get('action') == 'publish':
            status = 'publish'

        slug = form['title']
        if form.has_key('slug'):
            slug = form['slug']

        post = Post()
        post.title          = form['title']
        post.content        = form['content']
        post.folder_id      = form['folder']
        post.user_id        = g.user.id
        post.parent         = 0
        post.modified       = 'NOW()'
        post.created        = 'NOW()'
        post.excerpt        = post.get_excerpt()
        post.status         = status
        post.comment_status = 'open'
        post.comment_count  = 0
        post.slug           = slug
        post.guid           = post.guid_generate()

        Post.query.add(post)
        post_id = post.id
        post.create_revision()
        return post_id

    def create_revision(self):
        post        = self
        post.parent = post.id
        post.id     = ''
        post.guid   = post.guid_generate(rev=True)
        post.status = 'revision'
        Post.query.add(post)
        return True

    def guid_generate(self, rev=False):
        count = ''
        if rev:
            count = Folder.query.filter(id_parent=rev).count()
            count = '-'+str(count)

        path = Folder.query.get(self.folder_id)
        path = path.guid
        name = self.slug + count
        guid = url_unique(path+'/'+self.slug, Post)

        return guid


    def get_excerpt(self, size=255):
        # https://github.com/dziegler/excerpt_extractor/tree/master

        soup = Post.except_utils_rm_headers(BeautifulSoup(self.content))
        text = ''.join(soup.findAll(text=True)).split('\n')
        description = max((len(i.strip()),i) for i in text)[1].strip()[0:size]
        return description   
    
    @staticmethod
    def except_utils_rm_headers(soup):
        [[tree.extract() for tree in soup(elem)] for elem in ('h1','h2','h3','h4','h5','h6')]
        return soup

    def move(self):
        pass

    def add_revision(self):
        pass

    def get_revisions(self):
        pass

    def delete(self):
        pass

    def get_uid(self):
        pass

    def get_folders(self):
        pass

class Folder(fy_mysql.Base):
    # /sql/folder.sql
    folder_id               = fy_mysql.Column(etype='int', primary_key=True)
    folder_parent           = fy_mysql.Column(etype='int')
    folder_left             = fy_mysql.Column(etype='int')
    folder_right            = fy_mysql.Column(etype='int')
    folder_depth            = fy_mysql.Column(etype='int')
    folder_guid             = fy_mysql.Column(etype='string', unique=True)
    folder_slug             = fy_mysql.Column(etype='string', unique=True)
    folder_posts            = fy_mysql.Column(etype='int')
    folder_name             = fy_mysql.Column(etype='string', unique=True)
    folder_modified         = fy_mysql.Column(etype='datetime')
    folder_created          = fy_mysql.Column(etype='datetime')
    folder_content          = fy_mysql.Column(etype='string')
    folder_seo_content      = fy_mysql.Column(etype='string')

    @property
    def slug(self):
        if self.__dict__.has_key('slug'):
            return self.__dict__['slug']

    @slug.setter
    def slug(self, value):
        self.__dict__['slug'] = slugify(value)


    def update(self):
        Folder.query.update(self)
        self.build_guid()

    def update_guid(self):
        query = """
          SELECT
            GROUP_CONCAT(parent.folder_slug SEPARATOR '/') AS path
          FROM
            fypress_folder AS node,
            fypress_folder AS parent
          WHERE
            node.folder_left BETWEEN parent.folder_left AND parent.folder_right AND node.folder_id={0}
          ORDER BY
            parent.folder_left""".format(self.id)

        self.guid = url_unique(Folder.query.raw(query).one()[0]['path'], Folder, self.id)

        Folder.query.update(self)

    @staticmethod
    def build_guid():
        folders = Folder.query.get_all()
        for folder in folders:
            folder.update_guid()

    @staticmethod
    def get_all(html = False):
        query = """
            SELECT
                node.folder_seo_content,
                node.folder_created,
                node.folder_modified,
                node.folder_parent,
                node.folder_name,
                node.folder_depth,
                node.folder_posts,
                node.folder_id,
                node.folder_left,
                node.folder_content,
                node.folder_slug,
                node.folder_right
            FROM
                fypress_folder AS node,
                fypress_folder AS parent
            WHERE
                node.folder_left BETWEEN parent.folder_left AND parent.folder_right
            GROUP BY
                node.folder_id
            ORDER BY
                node.folder_left, node.folder_id
        """


        folders = Folder.query.sql(query).all(array=True)
        
        if not html:
            return folders
            
        tree = TreeHTML(folders)
        return tree.generate_folders_admin(False, 'sortable')

