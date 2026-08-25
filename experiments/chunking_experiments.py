# python experiments/chunking_experiments.py "data/Reincarnated as the Unlovable Villainess.pdf" 
import app.ingestion.extract as extract
import app.ingestion.chunk as chunk
from pathlib import Path
import matplotlib.pyplot as plt

if __name__ == "__main__":
    import sys

    path = Path(sys.argv[1])
    pages = extract.extract_pages(path)
    chunks = chunk.chunk_document(pages)

    for c in chunks:
        print(f"Chunk: {c.page_from}-{c.page_to}, {c.token_count} tokens, heading_path={c.heading_path}")
        print(c.content[:100])

    # Plot histogram of chunk sizes
    plt.hist([c.token_count for c in chunks], bins=20, edgecolor='black')
    plt.title(f'Histogram of Chunk Sizes (in Tokens) {path.name}')
    plt.xlabel('Number of Tokens')
    plt.ylabel('Frequency')
    plt.grid(axis='y', alpha=0.75)
    plt.savefig('debug/chunk_sizes.png')