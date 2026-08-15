from dotenv import load_dotenv
from sqlalchemy.dialects.postgresql import insert

try:
    from .embeddings import get_embeddings
    from .models import Document
except ImportError:  # pragma: no cover - allows running the module directly
    from embeddings import get_embeddings
    from models import Document


load_dotenv()



class VectorStore:

    def __init__(self, session):

        self.session = session

    
    def upsert(self, chunks):
        """
        It will take doc's chunks and upsert them into the dbafter embedding them.
        """

        if not chunks:
            return {"status": "success", "count": 0} # Return early if no chunks to process
        
        texts = [chunk["content"] for chunk in chunks] # Extract the text content from each chunk (assuming chunk is a dict with a "content" key)
        doc_embeddings = get_embeddings(texts) # Generete embeddings for all documents in a single batch request (more efficient than one-by-one)

        # Map payload into flat dictionaries matching the DB schema,
        # rows represent list of dicts be inserted into the database, with each dictionary corresponding to a row in the Document table.
        rows = [
            {
                # "id": c.get("id"),
                "content": c["content"],
                "source": c["source"],
                "chunk_index": c["chunk_index"],
                "embedding": e,
                "metadata_": c.get("metadata", {})
            }
            for c, e in zip(chunks, doc_embeddings)
        ]

        # Stage the initial batch insert
        db_upsert = insert(Document).values(rows) # it prepares an SQL INSERT statement for the Document table,Each dictionary corresponds to a row to be inserted into the database.
        # db_upsert contains the SQL statement that will be executed to insert the rows into the Document table. 

        # check for conflict on the id 
        db_upsert = db_upsert.on_conflict_do_update(
            index_elements = ["source", "chunk_index"], # specifies the column(s) that should be used to detect conflicts, id gets from the Document model(which is pk)
            set_ = {                 # contains dict of columns to update on conflict
                "content": db_upsert.excluded.content, # The excluded object represents the row that was proposed for insertion but was rejected due to a conflict.
                "embedding": db_upsert.excluded.embedding,
                "metadata_": db_upsert.excluded.metadata_,
            }    
        )

        try:
        # Execute everything in a single database round-trip
            db_result = self.session.execute(db_upsert) # db session executes the upsert statement, which will insert new rows or update existing rows based on the conflict
            self.session.commit() # commit the transaction to persist changes in the database
            return {"status": "success", "count": db_result.rowcount} 

        except Exception as e:
            self.session.rollback() # rollback the transaction in case of an error to maintain database integrity
            return {"status": "error", "message": str(e)} # Return an error message if something goes wrong


    def search(self, query, top_k=5, filters=None):
        
        """
        perform semantic search to find the most similar document based on the query and return top-k most similar documents 
        """
        q_embedding = get_embeddings([query])[0] # since get_embeddings returns a list of embeddings 
        distance = Document.embedding.cosine_distance(q_embedding) # returns a list of distances between the query embedding and each document embedding in the database, ordered by similarity (most similar first)

        db_query = self.session.query(Document, distance.label("distance")) # we are querying the Document table and also calculating the cosine distance between the query embedding and each document's embedding, labeling this distance as "distance" in the result set.

        """ 
        cosine_distance is a method(from pgvector-sqlalchemy) that measures the angle between two vectors, ignoring magnitude:
        It returns a list of distances between the query embedding and each document embedding in db,
        ordered by their similarity to the query in descending order (most similar first).
        This doesn't compute anything in Python. It builds a SQL expression object. When you use it in .order_by(distance), 
        SQLAlchemy compiles it into a SQL query that calculates the cosine distance in the database.
        """

        if filters:
            for key, value in filters.items():
                db_query = db_query.filter(Document.metadata_[key].astext == str(value)) # filter the query based on the provided metadata filters, converting the value to a string for comparison


        # Query the database for the top-k most similar documents
        rows = db_query.order_by(distance).limit(top_k).all() # it returns a list of Document objects that match the query and any filters applied.
        
        # Convert the results into a list of dictionaries so that they can be easily consumed by the caller.
        results = [
            {
                "id": doc.id,
                "content": doc.content,
                "metadata": doc.metadata_,
                "source": doc.source,
                "score": 1 - dist,  # Convert distance to similarity score (1 - distance)
            }
            for doc, dist in rows
        ]

        return results
    

    def delete(self, filters):

        """
        we are going to delet a certain document from db based on the filter provided by the user, 
        """
        try:
            if not filters:
                raise ValueError("Filters must be provided for deletion.")

            db_query = self.session.query(Document)

            for key, value in filters.items():
                db_query = db_query.filter(Document.metadata_[key].astext == str(value))

            counts = db_query.count() # count the number of documents that match the filters before deletion
            db_query.delete(synchronize_session=False) # synchronize_session=False avoids loading the deleted objects into the session, which can be more efficient for bulk deletions.
            self.session.commit()

            return {"status": "success", "count": counts}  # Return the number of rows deleted
       
        except Exception as e:

            self.session.rollback()
            return {"status": "error", "message": str(e)}  # Return an error message if something goes wrong

