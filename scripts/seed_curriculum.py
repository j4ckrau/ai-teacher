import os
from neo4j import GraphDatabase
from dotenv import load_dotenv, find_dotenv

# Load environment variables
load_dotenv(find_dotenv())

NEO4J_URI = os.getenv("NEO4J_URI", "bolt://localhost:7687")
NEO4J_USER = os.getenv("NEO4J_USER", "neo4j")
NEO4J_PASSWORD = os.getenv("NEO4J_PASSWORD", "password")

driver = GraphDatabase.driver(NEO4J_URI, auth=(NEO4J_USER, NEO4J_PASSWORD))

def seed_data(tx):
    # 1. Clear existing data
    tx.run("MATCH (n) DETACH DELETE n")
    
    # 2. Create Subjects
    tx.run("CREATE (s:Subject {id: 'math-8', title: '8th Grade Math', grade: 8})")
    tx.run("CREATE (s:Subject {id: 'sci-8', title: '8th Grade Science', grade: 8})")
    
    # 3. Create Units for Math
    tx.run("CREATE (u:Unit {id: 'math-8-alg', title: 'Introduction to Algebra'})")
    tx.run("MATCH (s:Subject {id: 'math-8'}), (u:Unit {id: 'math-8-alg'}) CREATE (u)-[:BELONGS_TO]->(s)")
    
    # 4. Create Lessons for Algebra Unit
    tx.run("CREATE (l:Lesson {id: 'math-8-alg-1', title: 'One-Step Equations', duration: 30})")
    tx.run("CREATE (l:Lesson {id: 'math-8-alg-2', title: 'Two-Step Equations', duration: 45})")
    tx.run("CREATE (l:Lesson {id: 'math-8-alg-3', title: 'Equations with Variables on Both Sides', duration: 60})")
    
    tx.run("MATCH (u:Unit {id: 'math-8-alg'}), (l:Lesson {id: 'math-8-alg-1'}) CREATE (l)-[:BELONGS_TO]->(u)")
    tx.run("MATCH (u:Unit {id: 'math-8-alg'}), (l:Lesson {id: 'math-8-alg-2'}) CREATE (l)-[:BELONGS_TO]->(u)")
    tx.run("MATCH (u:Unit {id: 'math-8-alg'}), (l:Lesson {id: 'math-8-alg-3'}) CREATE (l)-[:BELONGS_TO]->(u)")
    
    # 5. Create Prerequisites (Lessons)
    tx.run("MATCH (l1:Lesson {id: 'math-8-alg-1'}), (l2:Lesson {id: 'math-8-alg-2'}) CREATE (l2)-[:REQUIRES_MASTERY_OF]->(l1)")
    tx.run("MATCH (l2:Lesson {id: 'math-8-alg-2'}), (l3:Lesson {id: 'math-8-alg-3'}) CREATE (l3)-[:REQUIRES_MASTERY_OF]->(l2)")
    
    # 6. Create Concepts (Atomic learning units)
    tx.run("CREATE (c:Concept {id: 'alg-8-lin-eq-1', title: 'Addition Property of Equality', description: 'Solve x + a = b by subtracting a from both sides.'})")
    tx.run("MATCH (l:Lesson {id: 'math-8-alg-1'}), (c:Concept {id: 'alg-8-lin-eq-1'}) CREATE (c)-[:BELONGS_TO]->(l)")
    
    # 7. Add Science Units and Lessons
    tx.run("CREATE (u:Unit {id: 'sci-8-phy', title: 'Physical Science: Force and Motion'})")
    tx.run("MATCH (s:Subject {id: 'sci-8'}), (u:Unit {id: 'sci-8-phy'}) CREATE (u)-[:BELONGS_TO]->(s)")
    
    tx.run("CREATE (l:Lesson {id: 'sci-8-phy-1', title: 'Newtons Laws of Motion', duration: 60})")
    tx.run("MATCH (u:Unit {id: 'sci-8-phy'}), (l:Lesson {id: 'sci-8-phy-1'}) CREATE (l)-[:BELONGS_TO]->(u)")
    
    print("Seed data created successfully.")

if __name__ == "__main__":
    with driver.session() as session:
        session.execute_write(seed_data)
    driver.close()
