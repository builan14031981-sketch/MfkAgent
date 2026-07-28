import tiktoken


def count_tokens(text: str, model: str = "gpt-3.5-turbo") -> int:
    try:
        encoding = tiktoken.encoding_for_model(model)
    except KeyError:
        encoding = tiktoken.get_encoding("cl100k_base")
    return len(encoding.encode(text))


def count_messages_tokens(messages: list, model: str = "gpt-3.5-turbo") -> int:
    total = 0
    for msg in messages:
        total += count_tokens(msg.get("content", ""), model)
        total += 4
    total += 2
    return total
