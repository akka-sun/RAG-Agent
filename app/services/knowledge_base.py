class KnowledgeBaseError(Exception):
    pass


class KnowledgeBaseNotFoundError(KnowledgeBaseError):
    pass


class KnowledgeBaseNameConflictError(KnowledgeBaseError):
    pass