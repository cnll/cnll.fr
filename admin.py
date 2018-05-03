"""
Administration stuff.
"""
from flask import Blueprint, redirect, url_for, request, flash,\
    render_template, current_app
from flask.ext.login import LoginManager, UserMixin, login_user, \
    login_required, logout_user
from wtforms import Form, TextField, validators, PasswordField


bp = Blueprint("admin", __name__, url_prefix="/admin")
login_manager = LoginManager()


def setup(app):
  login_manager.init_app(app)
  app.register_blueprint(bp)


class login_form(Form):
  username = TextField('Username', [validators.Required()])
  password = PasswordField('Password', [validators.Required()])


class AdminUser(UserMixin):
  id = "admin"


@bp.route("/")
def home():
  return redirect(url_for(".login"))


@bp.route("/login", methods=["GET", "POST"])
def login():
  form = login_form(request.form)
  if request.method == 'POST' and form.validate():
    if form.password.data != current_app.config['PASSWORD']:
      flash("Invalid Login!", 'alert-failure')
      return redirect(url_for('login'))
    else:
      u = AdminUser()
      login_user(u)
      flash('You have been logged in!', 'alert-success')
      return redirect(url_for('home'))

  else:
    return render_template('login.html', form=form)


@bp.route('/logout')
@login_required
def logout():
  logout_user()
  flash('You were logged out', 'alert-success')
  return redirect(url_for('home'))


@login_manager.user_loader
def load_user(userid):
  print(userid)
  return AdminUser()
