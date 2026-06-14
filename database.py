import chromadb
from chromadb.utils.embedding_functions import SentenceTransformerEmbeddingFunction


def chroma_db_init():
    client = chromadb.PersistentClient(path="chroma_db")
    embedding_function = SentenceTransformerEmbeddingFunction(
        model_name="paraphrase-multilingual-MiniLM-L12-v2",
        device="cpu",
    )
    return client.get_or_create_collection(
        name="rag_collection",
        embedding_function=embedding_function,
    )


def _get_all_ids(collection):
    return set(collection.get(include=[]).get("ids", []))


def clear_collection(collection):
    ids = collection.get(include=[])["ids"]
    if ids:
        collection.delete(ids=ids)


def insert_into_collection_safe(collection, documents, ids, metadatas):
    existing_ids = _get_all_ids(collection)
    new_docs, new_ids, new_metas = [], [], []

    for doc, id_, meta in zip(documents, ids, metadatas):
        if id_ not in existing_ids:
            new_docs.append(doc)
            new_ids.append(id_)
            new_metas.append(meta)

    if new_docs:
        collection.add(documents=new_docs, ids=new_ids, metadatas=new_metas)


def db_query(collection, query_text, n_results=3, where_filter=None):
    query_params = {"query_texts": [query_text], "n_results": n_results}
    if where_filter:
        query_params["where"] = where_filter

    results = collection.query(**query_params)
    if results["documents"]:
        return results["documents"][0]
    return []


def db_get_by_control_ids(collection, control_ids):
    if not control_ids:
        return []

    where = {"control_id": control_ids[0]} if len(control_ids) == 1 else {"control_id": {"$in": control_ids}}
    results = collection.get(where=where)

    if results and results.get("documents"):
        return results["documents"]
    return []
