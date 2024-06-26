from modal import Stub, build, enter, method, web_endpoint,Image
from typing import Dict
import os
import modal
application_id_dict={}
image = Image.debian_slim().pip_install(
    "upstash_vector",
    "nltk"

)
stub = Stub(name="resume-parser", image=image)

@stub.function(secrets=[modal.Secret.from_name("Url"), modal.Secret.from_name("Token")],timeout=1000)
@web_endpoint(label="upsert",method="POST")
def upsert_data(requestData: Dict):
    from upstash_vector import Index
    from nltk.corpus import stopwords
    from collections import Counter
    data_list = requestData["data"]
    client_id = requestData["client"]
        
    URL = os.environ["Url"] 
    Token = os.environ["Token"] 
    app_id=0
    if client_id in application_id_dict:
        current_application_id = application_id_dict[client_id]
        app_id=current_application_id
    else:
        current_application_id = 0
        application_id_dict[client_id] = current_application_id
        app_id=current_application_id
        
    index = Index(url=URL, token=Token)
    for data in data_list:
        Email = data.get("Email", "")
        content = data.get("content", "")
        tokens = nltk.word_tokenize(content)
    
    # Remove stop words and punctuation
        stop_words = set(stopwords.words('english'))
        filtered_tokens = [token for token in tokens if token.lower() not in stop_words and token.isalnum()]
    
    # Perform part-of-speech tagging
        tagged_tokens = nltk.pos_tag(filtered_tokens)
    
    # Select relevant parts of speech (e.g., nouns and adjectives)
        relevant_tags = ['NN', 'NNS', 'NNP', 'NNPS', 'JJ']
        relevant_tokens = [token for token, tag in tagged_tokens if tag in relevant_tags]
    
    # Calculate word frequencies
        word_freq = Counter(relevant_tokens)
    
    # Select the most frequent words as keywords
        keywords = [word for word, freq in word_freq.most_common(200)]
    
        # Join the keywords into a string
        keyword_string = ', '.join(keywords)
        index.upsert(
            vectors=[
                    (f"{client_id}_{app_id}", keyword_string, {"clientID": client_id, "Email": Email, "content": content}),
                ]
            )
        application_id_dict[client_id] += 1
    return {"message": "Data upserted successfully"}

@stub.function()
@web_endpoint(label="match",method="POST")
def start_match(requestData: Dict):
    client=requestData["client"]
    data = requestData["data"]
    return (Model.query_data.remote(client,data))
    
    
@stub.cls(secrets=[modal.Secret.from_name("Url"), modal.Secret.from_name("Token")])
class Model:
    @build()
    @enter()
    def start_model(self):
        from upstash_vector import Index
        URL = os.environ["Url"] 
        Token = os.environ["Token"] 
        self.index = Index(url=URL, token=Token)

    @method()
    def query_data(self,client:str,data:str):
        filter = f"clientID = '{client}'" 
        result = self.index.query(
            data=data,
            filter=filter,
            top_k=5,
            include_vectors=False,
            include_metadata=True
        )
        
        info=[]
        for chunk in result:
            temp={"Email":chunk.metadata.get("Email"),"Content":chunk.metadata.get("content"),"Score":chunk.score}
            info.append(temp)
        if not info:
            return {"result":"NO data found"}
            
        return {"result":info}

