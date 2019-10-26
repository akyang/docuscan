import base64
import configparser
import qrcode
import requests
import uuid
import os

from docusign_esign import ApiClient, EnvelopesApi, EnvelopeDefinition, Signer, SignHere, Tabs, Recipients, Document
from flask import Flask, flash, request, redirect, url_for
from flask import make_response
from flask import render_template

config = configparser.ConfigParser()
config.read('config.ini')

ALLOWED_EXTENSIONS = set(['txt', 'pdf', 'htm', 'html'])

application = Flask(__name__)
application.config['UPLOAD_FOLDER'] = config['flask']['upload_folder']
application.config['EMBED_FOLDER'] = config['flask']['embed_folder']
application.config['QRCODE_FOLDER'] = config['flask']['qrcode_folder']
application.config['SECRET_KEY'] = config['flask']['secret']

signers = {'wluk@ucsd.edu': 'Winson Luk'}


def allowed_file(filename):
    return '.' in filename and \
           filename.rsplit('.', 1)[1].lower() in ALLOWED_EXTENSIONS


def embed_qrcode(filename):
    data = uuid.uuid4().hex
    qr = qrcode.make(data)
    qr_fname = data + '.png'
    qr_path = application.config['QRCODE_FOLDER'] + qr_fname
    qr.save(qr_path)

    encoded = base64.b64encode(open(qr_path, 'rb').read())

    file = open(application.config['UPLOAD_FOLDER'] + filename, 'r')
    content = file.read().rsplit('</body>', 1)
    img_tag = '<img src=\"data:image/png;base64,{qrcode}\">'.format(qrcode=encoded)
    embedded = content[0] + img_tag + '\n</body>' + content[1]
    f = open(application.config['EMBED_FOLDER'] + filename, 'w+')
    f.write(embedded)
    return f


def get_sender_account_info(token):
    return requests.get('https://account-d.docusign.com/oauth/userinfo', headers={'Authorization': 'Bearer ' + token}).json()


def make_envelope(file, sender, signer_name, signer_email, token):
    file.seek(0)
    content_bytes = file.read()
    base64_file_content = base64.b64encode(content_bytes).decode('ascii')

    document = Document(
        document_base64 = base64_file_content,
        name = 'DocuScan Terms',
        file_extension = 'html',
        document_id = 1
    )

    signer = Signer(
        email = signer_email,
        name = signer_name,
        recipient_id = '1',
        routing_order = '1'
    )

    envelope_definition = EnvelopeDefinition(
        email_subject = 'Please sign these terms',
        documents = [document],
        recipients = Recipients(signers = [signer]),
        status = 'sent'
    )

    api_client = ApiClient()
    api_client.host = 'https://demo.docusign.net/restapi'
    api_client.set_default_header('Authorization', 'Bearer ' + token)

    envelope_api = EnvelopesApi(api_client)
    results = envelope_api.create_envelope(sender['accounts'][0]['account_id'], envelope_definition=envelope_definition)
    print(results)
    return results


@application.route('/sign', methods=['GET', 'POST'])
def sign():
    print(request.args['code'])
    return 'rt'


@application.route('/', methods=['GET', 'POST'])
def auth():
    # redirect to authorize app
    url = 'https://account-d.docusign.com/oauth/auth?response_type={response}&scope={scope}&client_id={cid}&redirect_uri={redirect}'.format(
        response='code',
        scope='signature',
        cid=config['docusign']['integration'],
        redirect=config['docusign']['redirect']
    )
    return redirect(url)


@application.route('/upload', methods=['GET', 'POST'])
def upload_file():
    if request.method == 'POST':
        # check if the post request has the file part
        if 'file' not in request.files:
            flash('No file part')
            return redirect(request.url)
        if 'signer_name' not in request.form or 'signer_email' not in request.form:
            flash('No signer part')
            return redirect(request.url)
        file = request.files['file']
        signer_name = request.form['signer_name']
        signer_email = request.form['signer_email']
        filename = file.filename
        # if user does not select file, browser also
        # submit an empty part without filename
        if filename == '':
            flash('No selected file')
            return redirect(request.url)
        if file and allowed_file(filename) and signer_name:
            file.save(os.path.join(application.config['UPLOAD_FOLDER'], filename))
            embedded_file = embed_qrcode(filename)
            access_token = request.cookies['access_token']
            sender = get_sender_account_info(access_token)
            envelope = make_envelope(embedded_file, sender, signer_name, signer_email, access_token)
            return redirect(request.url)
    elif 'code' in request.args:
        code = request.args['code']
        url = 'https://account-d.docusign.com/oauth/token'
        auth = base64.b64encode(config['docusign']['integration'] + ':' + config['docusign']['secret'])
        header = {'Content-Type': 'application/x-www-form-urlencoded', 'Authorization': 'Basic ' + auth}
        data = {'grant_type': 'authorization_code', 'code': code, 'redirect_uri': config['docusign']['redirect']}
        response = requests.post(url, headers=header, data=data)
        page_resp = make_response(render_template('index.html'))
        page_resp.set_cookie('access_token', response.json()['access_token'])
        return page_resp
    return render_template('index.html')

if __name__ == '__main__':
    application.run(host='0.0.0.0', port=80)
