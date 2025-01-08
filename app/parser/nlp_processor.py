import spacy
import re

class NLPProcessor:
    def __init__(self):
        self.nlp = spacy.load("en_core_web_sm")
        
    def extract_name(self, text):
        doc = self.nlp(text.strip())
        for ent in doc.ents:
            if ent.label_ == "PERSON":
                return ent.text
        return None

    def extract_email(self, text):
        email_pattern = r'\b[A-Za-z0-9._%+-]+@[A-Za-z0-9.-]+\.[A-Z|a-z]{2,}\b'
        match = re.search(email_pattern, text)
        return match.group(0) if match else None

    def extract_phone(self, text):
        phone_pattern = r'\b\+?[\d\s-]{10,}\b'
        match = re.search(phone_pattern, text)
        return match.group(0) if match else None

    def extract_skills(self, text):
        # Add common skills keywords
        skills_keywords = {'python', 'java', 'javascript', 'sql', 'react', 'aws'}
        found_skills = set()
        
        doc = self.nlp(text.lower())
        for token in doc:
            if token.text in skills_keywords:
                found_skills.add(token.text)
        
        return list(found_skills)
