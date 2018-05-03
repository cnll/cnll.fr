#!/usr/bin/env python
# coding=utf-8

import mimetypes
from PIL import Image
import codecs
import locale
import os
from os.path import join
import re
from StringIO import StringIO
import datetime
from unicodedata import normalize

from argh import *
from fabric.api import local

from flask import (
    Flask,
    render_template,
    abort,
    make_response,
    request,
    redirect,
    url_for,
)
from flask.ext.frozen import Freezer
from flask.ext.flatpages import FlatPages, Page
from flask.ext.markdown import Markdown
from flask.ext.assets import Environment as AssetManager
from flask.ext.babel import Babel

# from raven.contrib.flask import Sentry

from admin import setup as admin_setup


# Configuration
import yaml


DEBUG = False
ASSETS_DEBUG = True
FLATPAGES_AUTO_RELOAD = False

BASE_URL = "http://www.cnll.fr"
FLATPAGES_EXTENSION = ".md"
FLATPAGES_ROOT = "pages"
BABEL_DEFAULT_LOCALE = "fr"


SECRET_KEY = "TODO"
PASSWORD = "TODO"


# App configuration
FEED_MAX_LINKS = 25
SECTION_MAX_LINKS = 12

REDIRECTS = {
    "membres": "/cnll/membres/",
    "principes-de-gouvernance-et-constitution-du-bureau-du-cnll": "/cnll/statuts/",
    "faq-cnll": "/cnll/faq/",
    "tags": "/news/",
    "node": "/news/",
    "taxonomy": "/news/",
    "events": "/news/",
    "presse": "/news/",
}

from local_config import *

###############################################################################
# Monkey patch

Page__init__orig = Page.__init__


def Page__init__(self, path, meta_yaml, body, html_renderer):
    Page__init__orig(self, path, meta_yaml, body, html_renderer)
    date = self.meta.get("date")

    if not date:
        self.meta["date"] = datetime.date.today()
    elif isinstance(date, str):
        year = int(date[0:4])
        month = int(date[5:7])
        day = int(date[8:10])
        date = datetime.date(year, month, day)
        self.meta["date"] = date

    if not self.meta.get("slug"):
        self.meta["slug"] = self.path.split("/")[-1]


Page.__init__ = Page__init__


###############################################################################
# Create app and services

app = Flask(__name__)
app.config.from_object(__name__)
pages = FlatPages(app)
freezer = Freezer(app)
markdown_manager = Markdown(app)
asset_manager = AssetManager(app)
babel = Babel(app)
# sentry = Sentry(app)

admin_setup(app)

###############################################################################
# Model helpers


def get_pages(offset=None, limit=None):
    """
  Retrieves pages matching passed criterias.
  """
    articles = list(pages)
    # assign section value if none was provided in the metas
    for article in articles:
        if not article.meta.get("section"):
            article.meta["section"] = article.path.split("/")[0]

    # filter unpublished article
    if not app.debug:
        articles = [p for p in articles if p.meta.get("draft") is not True]

    articles = sorted(articles, reverse=True, key=lambda p: p.meta["date"])

    if offset and limit:
        return articles[offset:limit]
    elif limit:
        return articles[:limit]
    elif offset:
        return articles[offset:]
    else:
        return articles


def get_posts(offset=None, limit=None):
    posts = list(pages)

    posts = [article for article in posts if article.path.startswith("news")]

    for post in posts:
        if not "image" in post.meta:
            post.meta["image"] = "news.jpg"

    # filter unpublished article
    # if not app.debug:
    #  posts = [p for p in posts if p.meta.get('draft') is False]

    # sort by date
    posts = sorted(posts, reverse=True, key=lambda p: p.meta["date"])

    if offset and limit:
        return posts[offset:limit]
    elif limit:
        return posts[:limit]
    elif offset:
        return posts[offset:]
    else:
        return posts


def get_publications():
    publications = [
        page for page in list(pages) if page.path.startswith("publications")
    ]

    publications = sorted(publications, reverse=True, key=lambda p: p.meta["date"])

    return publications


def get_years(pages):
    years = list(set([page.meta.get("date").year for page in pages]))
    years.reverse()
    return years


def slugify(text, delim=u"-"):
    """Generates an slightly worse ASCII-only slug."""
    _punct_re = re.compile(r'[\t !"#$%&\'()*\-/<=>?@\[\\\]^_`{|},.]+')
    result = []
    for word in _punct_re.split(text.lower()):
        word = normalize("NFKD", word).encode("ascii", "ignore")
        if word:
            result.append(word)
    return unicode(delim.join(result))


###############################################################################
# Filters


@app.template_filter()
def to_rfc2822(dt):
    if not dt:
        return
    current_locale = locale.getlocale(locale.LC_TIME)
    locale.setlocale(locale.LC_TIME, "en_US")
    formatted = dt.strftime("%a, %d %b %Y %H:%M:%S +0000")
    locale.setlocale(locale.LC_TIME, current_locale)
    return formatted


###############################################################################
# Context processors


@app.context_processor
def inject_ga():
    return dict(BASE_URL=BASE_URL)


@app.context_processor
def inject_recent_posts():
    return dict(recent_posts=get_posts())


@app.context_processor
def inject_publications():
    return dict(publications=get_publications())


###############################################################################
# Freezer helper


@freezer.register_generator
def url_generator():
    # URLs as strings
    yield "/fr/"


###############################################################################
# Routes


@app.route("/")
def home():
    template = "index.html"
    page = {"title": "CNLL"}
    return render_template(template, page=page)


@app.route("/<path:path>/")
def page(path=""):
    for orig, dest in REDIRECTS.items():
        if path.startswith(orig):
            return redirect(dest, 301)

    page = pages.get(path + "/index")
    if not page:
        page = pages.get(path)
    if not page:
        abort(404)
    template = page.meta.get("template", "_page.html")
    return render_template(template, page=page)


# Special pages


@app.route("/cnll/equipe/")
def equipe():
    yaml_data = yaml.safe_load(open(join(app.root_path, "data", "team.yml")))
    print(yaml_data)

    president = yaml_data["President"]
    vice_presidents = yaml_data["Vice-Presidents"]
    page = {"title": u"Notre équipe"}

    return render_template("equipe.html", **locals())


@app.route("/news/")
def news():
    posts = get_posts()
    page = {"title": "News"}
    return render_template("news.html", **locals())


@app.route("/positions/")
def positions():
    publications = get_publications()
    page = pages.get("positions/index")
    return render_template("positions.html", **locals())


@app.route("/news/<path:slug>/")
def post(slug):
    page = pages.get("news/" + slug)
    if not page:
        return redirect(url_for("news"))

    recent_posts = get_posts()
    return render_template("post.html", **locals())


# Aux


@app.route("/image/<path:path>")
def image(path):
    if ".." in path:
        abort(500)
    fd = open(join(app.root_path, "images", path))
    data = fd.read()

    hsize = int(request.args.get("h", 0))
    vsize = int(request.args.get("v", 0))
    if hsize > 1000 or vsize > 1000:
        abort(500)

    if hsize:
        image = Image.open(StringIO(data))
        x, y = image.size

        x1 = hsize
        y1 = int(1.0 * y * hsize / x)
        image.thumbnail((x1, y1), Image.ANTIALIAS)
        output = StringIO()
        image.save(output, "PNG")
        data = output.getvalue()
    if vsize:
        image = Image.open(StringIO(data))
        x, y = image.size

        x1 = int(1.0 * x * vsize / y)
        y1 = vsize
        image.thumbnail((x1, y1), Image.ANTIALIAS)
        output = StringIO()
        image.save(output, "PNG")
        data = output.getvalue()

    response = make_response(data)
    response.headers["content-type"] = mimetypes.guess_type(path)
    return response


@app.route("/feed")
def feed():
    pages = get_posts(limit=FEED_MAX_LINKS)
    now = datetime.datetime.now()

    resp = make_response(render_template("base.rss", **locals()))
    resp.headers["Content-Type"] = "text/xml"
    return resp


@app.route("/sitemap.xml")
def sitemap():
    today = datetime.date.today()
    recently = datetime.date(year=today.year, month=today.month, day=1)
    pages = get_pages()

    resp = make_response(render_template("sitemap.xml", **locals()))
    resp.headers["Content-Type"] = "text/xml"
    return resp


@app.errorhandler(404)
def page_not_found(error):
    page = {"title": "Page introuvable"}
    return render_template("404.html", page=page), 404


# Not needed currently since we don't do static generation (yet?)
@app.route("/403.html")
def error403():
    return render_template("403.html")


@app.route("/404.html")
def error404():
    return render_template("404.html")


@app.route("/500.html")
def error500():
    return render_template("500.html")


###############################################################################
# Commands


@command
def build():
    """ Builds this site.
  """
    print("Building website...")
    app.debug = False
    asset_manager.config["ASSETS_DEBUG"] = False
    freezer.freeze()
    local("cp ./static/*.ico ./build/")
    local("cp ./static/*.txt ./build/")
    local("cp ./static/*.xml ./build/")
    print("Done.")


# Not used (yet?)
@command
def post(section, title=None, filename=None):
    """ Create a new empty post.
  """
    if not os.path.exists(os.path.join(FLATPAGES_ROOT, section)):
        raise CommandError(u"Section '%s' does not exist" % section)
    post_date = datetime.datetime.today()
    title = unicode(title) if title else "Untitled Post"
    if not filename:
        filename = u"%s.md" % slugify(title)
    year = post_date.year
    pathargs = [section, str(year), filename]
    filepath = os.path.join(
        os.path.abspath(os.path.dirname(__file__)), FLATPAGES_ROOT, "/".join(pathargs)
    )
    if os.path.exists(filepath):
        raise CommandError("File %s exists" % filepath)
    content = "\n".join(
        [
            u"title: %s" % title,
            u"date: %s" % post_date.strftime("%Y-%m-%d"),
            u"published: false\n\n",
        ]
    )
    try:
        codecs.open(filepath, "w", encoding="utf8").write(content)
        print(u"Created %s" % filepath)
    except Exception as error:
        raise CommandError(error)


@command
def serve(server="0.0.0.0", port=7000):
    """ Serves this site.
  """
    debug = app.config["DEBUG"] = app.debug = True
    # asset_manager.config['ASSETS_DEBUG'] = debug
    app.run(host=server, port=port, debug=debug)


if __name__ == "__main__":
    parser = ArghParser()
    parser.add_commands([build, post, serve])
    parser.dispatch()
