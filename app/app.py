from flask import Flask, request, jsonify
from werkzeug.utils import secure_filename
import os
from app.config import Config
from app.models import db, Resume
from app.parser.pdf_parser import PDFParser
from app.parser.docx_parser import DOCXParser
from app.parser.nlp_processor import NLPProcessor

app = Flask(__name__)
app.config.from_object(Config)
db.init_app(app)

pdf_parser = PDFParser()
docx_parser = DOCXParser()
nlp_processor = NLPProcessor()

@app.route('/parse', methods=['POST'])
def parse_resume():
    if 'file' not in request.files:
        return jsonify({'error': 'No file provided'}), 400
        
    file = request.files['file']
    if file.filename == '':
        return jsonify({'error': 'No file selected'}), 400
        
    if file and allowed_file(file.filename):
        filename = secure_filename(file.filename)
        filepath = os.path.join(app.config['UPLOAD_FOLDER'], filename)
        file.save(filepath)
        
        # Parse file based on extension
        if filename.endswith('.pdf'):
            text = pdf_parser.parse(filepath)
        else:
            text = docx_parser.parse(filepath)
            
        # Extract information
        name = nlp_processor.extract_name(text)
        email = nlp_processor.extract_email(text)
        phone = nlp_processor.extract_phone(text)
        skills = nlp_processor.extract_skills(text)
        
        # Save to database
        resume = Resume(
            filename=filename,
            candidate_name=name,
            email=email,
            phone=phone,
            skills=skills
        )
        db.session.add(resume)
        db.session.commit()
        
        os.remove(filepath)  # Clean up uploaded file
        
        return jsonify({
            'name': name,
            'email': email,
            'phone': phone,
            'skills': skills
        })
        
    return jsonify({'error': 'Invalid file type'}), 400

def allowed_file(filename):
    return '.' in filename and \
           filename.rsplit('.', 1)[1].lower() in app.config['ALLOWED_EXTENSIONS']

if __name__ == '__main__':
    with app.app_context():
        db.create_all()
    app.run(debug=True)
