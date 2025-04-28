
def display_graph(graph, file_path = 'output_image.png'):
    output = graph.get_graph().draw_mermaid_png()

    # Write the PNG data to the file
    with open(file_path, 'wb') as f:
        f.write(output)

    print(f"Image saved as {file_path}")