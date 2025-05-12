from src.mastercard_solution_tech_stack_agent.utilities.vectorstore_builder import build_faiss_vectorstore

# You can add new text files here to include them in the vectorstore.
# This will allow the model to reference the new information.
# You can always change the file directory if the file is not in the project directory.
build_faiss_vectorstore(
    ["docs/kb.txt", "docs/meta_guidance.txt"]  # <— this is the new addition
)
