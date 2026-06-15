import uuid
import os
from neo4j import GraphDatabase
from dotenv import load_dotenv
load_dotenv()  # Load environment variables from .env file
NEO4J_URI = os.getenv("NEO4J_URI")
NEO4J_USER = os.getenv("NEO4J_USER")
NEO4J_PASSWORD = os.getenv("NEO4J_PASSWORD")

class ManualGraphConnector:
    def __init__(self, uri, user, password):
        """Initializes the Neo4j database driver."""
        self.driver = GraphDatabase.driver(uri, auth=(user, password))

    def close(self):
        """Closes the database driver connection."""
        self.driver.close()

    def create_constraints(self):
        """Creates uniqueness constraints to optimize lookups and prevent duplicates."""
        with self.driver.session() as session:
            # Ensure Manual titles and Chunk IDs are unique
            session.run("CREATE CONSTRAINT FOR (m:Manual) REQUIRE m.title IS UNIQUE IF NOT EXISTS")
            session.run("CREATE CONSTRAINT FOR (c:Chunk) REQUIRE c.id IS UNIQUE IF NOT EXISTS")
            print("Successfully verified/created database constraints.")

    def ingest_manual_chunks(self, manual_title, product_type, chunks_list):
        """
        Ingests a list of text chunks for a specific manual, creating the hierarchy 
        and the sequential sequential [:NEXT_CHUNK] relationships.
        
        chunks_list expects a list of dictionaries: 
        [{"text": "...", "page": 1, "keywords": ["engine", "oil"]}, ...]
        """
        query = """
        MERGE (m:Manual {title: $manual_title})
        ON CREATE SET m.product_type = $product_type, m.created_at = timestamp()
        
        WITH m
        UNWIND $chunks AS chunk_data
        CREATE (c:Chunk {id: chunk_data.id})
        SET c.text = chunk_data.text,
            c.page = chunk_data.page,
            c.keywords = chunk_data.keywords
            
        MERGE (m)-[:HAS_CHUNK]->(c)
        WITH m, c ORDER BY c.page ASC
        
        // Collect chunks to stitch them together sequentially
        WITH m, collect(c) AS chunks
        UNWIND range(0, size(chunks) - 2) AS idx
        WITH chunks[idx] AS current_chunk, chunks[idx+1] AS next_chunk
        MERGE (current_chunk)-[:NEXT_CHUNK]->(next_chunk)
        """
        
        # Pre-assign unique UUIDs to chunks before ingestion
        processed_chunks = []
        for chunk in chunks_list:
            chunk_copy = chunk.copy()
            chunk_copy['id'] = str(uuid.uuid4())
            processed_chunks.append(chunk_copy)

        with self.driver.session() as session:
            session.run(
                query, 
                manual_title=manual_title, 
                product_type=product_type, 
                chunks=processed_chunks
            )
        print(f"Successfully ingested '{manual_title}' with {len(chunks_list)} chunks.")

    def link_interconnections_by_keyword(self, keyword, relationship_reason="SHARED_KEYWORD"):
        """
        Finds chunks across DIFFERENT manuals that share a specific keyword 
        (e.g., 'spark plug' or 'P0302') and draws an interconnection link between them.
        """
        query = """
        MATCH (c1:Chunk), (c2:Chunk)
        WHERE c1.id < c2.id  // Prevents duplicate bidirectional links and self-matching
          AND $keyword IN c1.keywords 
          AND $keyword IN c2.keywords
        
        // Ensure they belong to different manuals
        MATCH (m1:Manual)-[:HAS_CHUNK]->(c1)
        MATCH (m2:Manual)-[:HAS_CHUNK]->(c2)
        WHERE m1 <> m2
        
        // Create the interconnection
        MERGE (c1)-[r:REFERENCES {reason: $reason, keyword: $keyword}]->(c2)
        RETURN m1.title AS source_manual, m2.title AS target_manual, count(r) AS links_created
        """
        with self.driver.session() as session:
            result = session.run(query, keyword=keyword, reason=relationship_reason)
            for record in result:
                print(f"Interconnected {record['source_manual']} <--> {record['target_manual']} via keyword: '{keyword}'")


# =====================================================================
# EXAMPLE USAGE
# =====================================================================
if __name__ == "__main__":
    # Replace with your actual Neo4j credentials
   
    # Initialize the connection
    db = ManualGraphConnector(NEO4J_URI, NEO4J_USER, NEO4J_PASSWORD)
    
    try:
        # 1. Setup constraints
        db.create_constraints()
        
    finally:
        db.close()
        print("\nDatabase driver connection closed.")