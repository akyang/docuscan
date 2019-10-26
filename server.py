import configparser
import qrcode
import uuid
import os
from flask import Flask, flash, request, redirect, url_for
from flask import render_template

config = configparser.ConfigParser()
config.read('config.ini')

ALLOWED_EXTENSIONS = set(['txt', 'pdf', 'htm', 'html'])

app = Flask(__name__)
app.config['UPLOAD_FOLDER'] = config['flask']['upload_folder']
app.config['EMBED_FOLDER'] = config['flask']['embed_folder']
app.config['QRCODE_FOLDER'] = config['flask']['qrcode_folder']
app.config['SECRET_KEY'] = config['flask']['secret']


def allowed_file(filename):
    return '.' in filename and \
           filename.rsplit('.', 1)[1].lower() in ALLOWED_EXTENSIONS


def embed_qrcode(filename):
    data = uuid.uuid4().hex
    qr = qrcode.make(data)
    qr_fname = data + '.png'
    qr_path = app.config['QRCODE_FOLDER'] + qr_fname
    qr.save(qr_path)

    file = open(app.config['UPLOAD_FOLDER'] + filename, 'r')
    content = file.read().rsplit('</body>', 1)
    img_tag = '<img src=\"{qrcode}\">'.format(qrcode= '../' + qr_path)
    embedded = content[0] + img_tag + '\n</body>' + content[1]
    f = open(app.config['EMBED_FOLDER'] + filename, 'w+')
    f.write(embedded)
    return f


@app.route('/', methods=['GET', 'POST'])
def upload_file():
    if request.method == 'POST':
        # check if the post request has the file part
        if 'file' not in request.files:
            flash('No file part')
            return redirect(request.url)
        file = request.files['file']
        filename = file.filename
        # if user does not select file, browser also
        # submit an empty part without filename
        if filename == '':
            flash('No selected file')
            return redirect(request.url)
        if file and allowed_file(filename):
            file.save(os.path.join(app.config['UPLOAD_FOLDER'], filename))
            embedded_file = embed_qrcode(filename)
            return redirect(request.url)
    return render_template('index.html')

if __name__ == '__main__':
    app.run()
