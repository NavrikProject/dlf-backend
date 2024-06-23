import os
import tempfile
from flask import Flask, request, jsonify
from flask_cors import CORS
from google.oauth2 import service_account
from googleapiclient.discovery import build
from googleapiclient.http import MediaFileUpload

app = Flask(__name__)
CORS(app)

# Get the current working directory
current_dir = os.getcwd()
print("Current Directory:", current_dir)

# Join paths dynamically
file_path = os.path.join(current_dir, 'subdir', 'filename.txt')
print("Dynamic File Path:", file_path)

def authenticate_google_services():
    # Authentication logic for Google Drive and Docs API
    SCOPES = ['https://www.googleapis.com/auth/drive', 'https://www.googleapis.com/auth/documents']
    credentials = service_account.Credentials.from_service_account_file(file_path, scopes=SCOPES)
    drive_service = build('drive', 'v3', credentials=credentials)
    docs_service = build('docs', 'v1', credentials=credentials)
    return drive_service, docs_service

def extract_text_from_pdf(drive_service, docs_service, pdf_file_path):
    try:
        # Upload PDF to Google Drive
        file_metadata = {'name': 'Uploaded PDF', 'mimeType': 'application/pdf'}
        media = MediaFileUpload(pdf_file_path, mimetype='application/pdf', resumable=True)
        print(f"Sending file '{pdf_file_path}' to Google Drive API")
        
        upload_response = drive_service.files().create(body=file_metadata, media_body=media, fields='id').execute()
        file_id = upload_response.get('id')
        
        if not file_id:
            raise Exception("Failed to upload the PDF to Google Drive.")
        
        print(f"File uploaded successfully. Google Drive File ID: {file_id}")
        
        # Convert the uploaded PDF to a Google Doc
        export_mime_type = 'application/vnd.google-apps.document'
        copy_response = drive_service.files().copy(fileId=file_id, body={'mimeType': export_mime_type}).execute()
        doc_id = copy_response.get('id')
        
        if not doc_id:
            raise Exception("Failed to convert the PDF to Google Docs format.")
        
        print(f"PDF converted to Google Doc successfully. Google Doc ID: {doc_id}")
        
        # Retrieve text content from the Google Doc
        doc = docs_service.documents().get(documentId=doc_id).execute()
        doc_content = doc.get('body').get('content')
        print(f"Retrieving text content from Google Doc (ID: {doc_id})")
        
        # Extract text from the content
        extracted_text = ''
        for element in doc_content:
            if 'paragraph' in element:
                for paragraph in element['paragraph']['elements']:
                    extracted_text += paragraph.get('textRun', {}).get('content', '')

        return extracted_text

    except Exception as e:
        raise Exception(f'Error extracting text from PDF: {str(e)}')

@app.route('/upload', methods=['POST'])
def upload_file():
    try:
        if 'file' not in request.files:
            print("No file part in the request")
            return jsonify({"error": "No file part"}), 400

        file = request.files['file']
        if file.filename == '':
            print("No file selected for uploading")
            return jsonify({"error": "No selected file"}), 400

        print(f"File uploaded: {file.filename}")

        # Save the file to a temporary location
        temp_dir = tempfile.gettempdir()
        pdf_file_path = os.path.join(temp_dir, file.filename)
        file.save(pdf_file_path)

        # Authenticate Google Docs API
        drive_service, docs_service = authenticate_google_services()

        # Extract text from PDF
        try:
            extracted_text = extract_text_from_pdf(drive_service, docs_service, pdf_file_path)
            print(f"Text extracted successfully from PDF: {file.filename}")
            return jsonify({"message": f"File '{file.filename}' uploaded and text extracted successfully.",
                            "extracted_text": extracted_text}), 200
        except Exception as extraction_error:
            print(f"Error extracting text from PDF: {str(extraction_error)}")
            return jsonify({"error": f"Error extracting text from PDF: {str(extraction_error)}"}), 500
        finally:
            # Clean up the temporary file
            if os.path.exists(pdf_file_path):
                os.remove(pdf_file_path)

    except Exception as upload_error:
        print(f"Error processing upload: {str(upload_error)}")
        return jsonify({"error": f"Error processing upload: {str(upload_error)}"}), 500

if __name__ == '__main__':
    app.run(debug=True)
