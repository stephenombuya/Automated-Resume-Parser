# Automated Resume Parser

A Python-based application that automatically extracts and analyzes information from resume documents (PDF and DOCX formats) using natural language processing.

## Features

- **Multiple Format Support**: Parse resumes in PDF and DOCX formats
- **Intelligent Information Extraction**: Extract key details including:
  - Candidate name
  - Email address
  - Phone number
  - Skills
- **Database Storage**: Automatically store parsed information in PostgreSQL database
- **RESTful API**: Simple API endpoint for resume parsing
- **Scalable Architecture**: Modular design for easy extensions and modifications

## Technology Stack

- **Backend**: Python 3.9+, Flask
- **Database**: PostgreSQL
- **NLP**: SpaCy
- **Document Processing**: PyPDF2, python-docx
- **Development Tools**: pytest, black, flake8

## Installation

1. Clone the repository:
```bash
git clone https://github.com/stephenombuya/Automated-Resume-Parser
cd resume-parser
```

2. Create and activate a virtual environment:
```bash
python -m venv venv
source venv/bin/activate  # On Windows: venv\Scripts\activate
```

3. Install dependencies:
```bash
pip install -r requirements.txt
```

4. Download SpaCy model:
```bash
python -m spacy download en_core_web_sm
```

5. Set up environment variables:
```bash
cp .env.example .env
# Edit .env with your database credentials
```

6. Initialize the database:
```bash
flask db upgrade
```

## Usage

1. Start the Flask application:
```bash
python app.py
```

2. Send a POST request to parse a resume:
```bash
curl -X POST -F "file=@/path/to/resume.pdf" http://localhost:5000/parse
```

### Example Response

```json
{
    "name": "John Doe",
    "email": "john.doe@email.com",
    "phone": "+1 123-456-7890",
    "skills": ["python", "java", "sql"]
}
```

## Project Structure

```
resume-parser/
├── app/
│   ├── __init__.py
│   ├── config.py
│   ├── models.py
│   ├── parser/
│   │   ├── pdf_parser.py
│   │   ├── docx_parser.py
│   │   └── nlp_processor.py
│   └── utils.py
├── tests/
├── requirements.txt
├── .env.example
└── README.md
```

## Development

- Run tests:
```bash
pytest
```

- Format code:
```bash
black .
```

- Check code style:
```bash
flake8
```

## Contributing

1. Fork the repository
2. Create your feature branch: `git checkout -b feature/new-feature`
3. Commit your changes: `git commit -am 'Add new feature'`
4. Push to the branch: `git push origin feature/new-feature`
5. Submit a pull request

## License

This project is licensed under the MIT License - see the `LICENSE` file for details.

## Acknowledgments

- SpaCy for providing excellent NLP capabilities
- PyPDF2 and python-docx for document parsing functionality

## Future Improvements

- Add support for more document formats
- Implement machine learning for better information extraction
- Add bulk processing capabilities
- Create a web interface for file uploads
- Enhance skills detection with industry-specific vocabularies
- Add export functionality to various formats
