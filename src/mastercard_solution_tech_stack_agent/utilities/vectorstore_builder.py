from typing import List
from langchain.document_loaders import TextLoader
from langchain.text_splitter import RecursiveCharacterTextSplitter
from langchain_community.vectorstores import FAISS
from langchain_openai import OpenAIEmbeddings


def build_faiss_vectorstore(
    input_paths: List[str],
    persist_path: str = "src/services/techstack_agent_module/kb_vectorstore",
    chunk_size: int = 500,
    chunk_overlap: int = 100,
):
    documents = []
    for path in input_paths:
        loader = TextLoader(path)
        documents += loader.load()

    splitter = RecursiveCharacterTextSplitter(
        chunk_size=chunk_size, chunk_overlap=chunk_overlap
    )
    chunks = splitter.split_documents(documents)

    embeddings = OpenAIEmbeddings()
    vectorstore = FAISS.from_documents(chunks, embeddings)
    vectorstore.save_local(persist_path)
