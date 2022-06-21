from missive import load_converstations, load_messages

cache_dir = "missive.cache.d"

for convo in load_converstations(cache_dir):
    messages = load_messages(cache_dir, convo["id"])
    print(f"{convo['id']=} {len(messages)=} loaded")
