import fitz
from openai import OpenAI
import os
import requests
import hashlib

class OpenAIPapersParser:
    def __init__(self, gpt_model="gpt-4"):
        self.client = OpenAI(
            api_key= os.environ.get("OPENAI_API_KEY")
        )

        self.gpt_model = gpt_model
        # Create the tmp folder if it does not exist
        os.makedirs("tmp", exist_ok=True)

    def calculate_hash(self, file_path_url):
        hash_object = hashlib.sha256(file_path_url.encode())
        hash_value = hash_object.hexdigest()
        return hash_value

    def get_first_page_text(self, file_path_url):
        """
        1. Download the PDF file from the URL and store to /tmp. Set as title the hash of the file_path_url
        2. Parse the PDF using fitz
        3. Extract the text from the first page
        """
        # Calculate the hash of the file_path_url
        file_path_url_hash = self.calculate_hash(file_path_url)
        file_path = f"tmp/{file_path_url_hash}.pdf"
        with open(file_path, "wb") as f:
            response = requests.get(file_path_url)
            f.write(response.content)
        doc = fitz.open(file_path)
        first_page = doc.load_page(0)

        return first_page.get_text()
    
    def send_request_to_openai(self, prompt):
        chat_completion = self.client.chat.completions.create(
            messages=[
                {
                    "role": "user",
                    "content": prompt,
                }
            ],
            model=self.gpt_model
        )
        return chat_completion.choices[0].message.content
            
    def extract_title(self, file_path_url):
        text = self.get_first_page_text(file_path_url)
        prompt = f"""Your are an expert in the field of Paper Semantification.
        Your job is to extract the title from the first page of the paper given in the following text.
        Only ouptut the title. Do not output any other boilerplate text.
        Text: {text}
        """
        paper_title = self.send_request_to_openai(prompt)
        return paper_title

    def extract_authors_metadata(self, file_path_url):
        text = self.get_first_page_text(file_path_url)
        prompt = f"""Your are an expert in the field of Paper Semantification.
        Your job is to extract the authors, their affiliations and emails from the first page of the paper given in the following text.
        Be especially careful with the interpreation of german umlauts (ä, ö, ü, ß) and special characters (e.g. é, è, ç, ñ, etc.). For example, the name Konrad U. F¨orstner should be interpreted as Konrad U. Förstner.
        Do not try to come up with the emails yourself, just extract them from the text. If you cannot find an email, just leave it empty.
        Write the output as a list of dictionaries in the following format for each author: 
        [\{{"name": "John Doe", "affiliation": ["University of Oxford", "Stanford University"], "email": ["john.doe@oxford.com", "john.doe@stanford.edu.com"]}}, 
        {{"name": "Jane Doe", "affiliation": ["University of Cambridge"], "email": ["Jane.doe@oxford.com"]}}]
        \n\nText: {text}
        """
        paper_authors = self.send_request_to_openai(prompt)
        return paper_authors
    
    def format_json_authors(self, paper_authors_str: str):
        """
        In case the extracted authors from the main prompt are not output in the appropriate format,
        and eval fails, send another request to OpenAI to format the authors
        """
        prompt = f"""
        Given the following string of authors, format it as a list of dictionaries in the following format for each author.
        The main goal is to successfully run eval function in python on the output of this request.
        {paper_authors_str}    
        """
        paper_authors_refined = self.send_request_to_openai(prompt)
        return paper_authors_refined
    
    def parse_authors(self, file_path_url):
        paper_authors = self.extract_authors_metadata(file_path_url)
        paper_authors = paper_authors.replace('\n', '')
        try:
            paper_authors_json = eval(paper_authors)
        except Exception as e:
            # Backup plan: if eval fails, ask OpenAI to format the authors
            print(f"Exception: {e}")
            print("Failed to parse the authors string. Asking OpenAI to format it.")
            paper_authors_refined = self.format_json_authors(paper_authors)
            paper_authors_json = eval(paper_authors_refined)
        return paper_authors_json




if __name__ == "__main__":
    parser = OpenAIPapersParser()
    file_path_url = "http://ceurspt.wikidata.dbis.rwth-aachen.de/Vol-2451/paper-23.pdf"
    paper_title = parser.extract_title(file_path_url)
    print(paper_title)
    # Output: "Take it Personally - A Python library for data enrichment in informetrical applications"
    paper_authors = parser.parse_authors(file_path_url)
    print(paper_authors)