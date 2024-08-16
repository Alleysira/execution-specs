# Import necessary modules
from scalpel.cfg import CFGBuilder, Link
import tokenize
from io import StringIO
import ast
import os

def remove_comments(source):
    result = []
    tokens = tokenize.generate_tokens(StringIO(source).readline)
    
    prev_end = (1, 0)
    
    for token_type, token_string, start, end, line in tokens:
        if start[0] > prev_end[0]:
            result.append('\n' * (start[0] - prev_end[0] - 1))
            result.append(' ' * start[1])
        elif start[1] > prev_end[1]:
            result.append(' ' * (start[1] - prev_end[1]))

        if token_type == tokenize.COMMENT:
            prev_end = end
            continue
        elif token_type == tokenize.STRING:
            if token_string.startswith(('"""', "'''")) and (line.lstrip().startswith(token_string)):
                prev_end = end
                continue
        result.append(token_string)
        prev_end = end
    
    return ''.join(result)

def get_funName(file_path):
    with open(file_path, 'r', encoding='utf-8') as file:
        tree = ast.parse(file.read(), filename=file_path)

    function_names = [node.name for node in ast.walk(tree) if isinstance(node, ast.FunctionDef)]
    return function_names

def generate_cfg(src:str,opFuncName:list,opcode_class:str):
    opcode_func_name = opFuncName
    for opcode_func_name in opcode_func_name:
        cfg = CFGBuilder().build_from_src(opcode_func_name, src, False)
        # Initialize the CFGs
        opcode_cfg = None 

        # Collect CFGs for all functions
        function_cfgs = {}

        # Dictionary to track call counts and existing edges
        call_counts = {}
        edges = {}

        for (block_id, fun_name), fun_cfg in cfg.functioncfgs.items():
            function_cfgs[fun_name] = fun_cfg
            if fun_name == opcode_func_name:
                opcode_cfg = fun_cfg

            # Automatically connect all function calls in get_byte to their CFGs
        if opcode_cfg:
            combined_graph = opcode_cfg._build_visual(format='png', calls=False)
            
            for block in opcode_cfg:
                existing_edges = set()
                if block.func_calls:
                    for call in block.func_calls:
                        called_func_name = call['name']
                        if called_func_name in function_cfgs:
                            called_cfg = function_cfgs[called_func_name]
                            entry_block = called_cfg.entryblock

                            # Track the call count
                            if called_func_name not in call_counts:
                                call_counts[called_func_name] = 0
                            call_counts[called_func_name] += 1

                            # Edge key
                            edge_key = (str(block.id), str(entry_block.id))

                            # Check if the edge already exists and update its label if it does
                            if edge_key not in edges:
                                # Add new edge
                                combined_graph.edge(*edge_key, style="dashed",
                                                    label=f"calls {called_func_name}")
                                edges[edge_key] = (block.id, entry_block.id,called_func_name,call_counts[called_func_name])

                            # Add a link from the current block to the entry block of the called function
                            new_link = Link(block, entry_block)
                            if new_link not in block.exits:
                                block.exits.append(new_link)
                                entry_block.predecessors.append(new_link)

                            # Add a subgraph for the called function
                            with combined_graph.subgraph(name=f'cluster_{called_func_name}') as c:
                                c.attr(label=f'{called_func_name} function', color='black')
                                
                                for called_block in called_cfg.get_all_blocks():
                                    node_id = str(called_block.id)
                                    if node_id not in combined_graph:
                                        c.node(node_id, label=called_block.get_source())

                                    for exit in called_block.exits:
                                        edge = (str(called_block.id), str(exit.target.id))
                                        if edge not in existing_edges:
                                            c.edge(*edge, label=exit.get_exitcase().strip())
                                            existing_edges.add(edge)  # Mark this edge as added

            combined_graph.render("./opcodes_icfg/" +opcode_class +'/' + opcode_func_name, cleanup=False)

# can't deal with class definition
def read_pyfile_skip_class(input_path):
    result = []
    skip_class = False
    class_indent = None

    with open(input_path, 'r') as file:
        # 使用 tokenize 模块来处理文件
        tokens = tokenize.generate_tokens(file.readline)
        indent_stack = []

        for token_type, token_string, start, end, line in tokens:
            if token_type == tokenize.INDENT:
                indent_stack.append(token_string)
            elif token_type == tokenize.DEDENT:
                if indent_stack:
                    indent_stack.pop()
            elif token_type == tokenize.NAME and token_string == "class":
                skip_class = True
                class_indent = len(indent_stack)
                result.append(line)
                continue
            elif token_type == tokenize.STRING:
                # 处理多行注释
                result.append(line)
                continue
            elif token_type == tokenize.COMMENT:
                # 跳过注释行
                continue

            if skip_class:
                current_indent = len(indent_stack)
                if current_indent <= class_indent:
                    skip_class = False
                continue

            if not skip_class:
                result.append(line)

    return ''.join(result)

def invalid_files_check(input):
    useless_file = ["__init__","exception"]
    for name in useless_file:
        if name in input:
            return False
    return True

def get_src(opclass):
    # Read and preprocess the source files
    src = ""
    with open('../src/ethereum/cancun/vm/instructions/' + opclass + '.py','r', encoding='utf-8') as f:
        src = f.read()

    vm_path = "../src/ethereum/cancun/vm"
    for file in os.listdir(vm_path):
        file_path = os.path.join(vm_path, file)
        if os.path.isfile(file_path) and invalid_files_check(file_path):  # 只包含文件，不包含文件夹

            with open(file_path,'r',encoding='utf-8') as f:
                src += f.read()
    src = remove_comments(src)
    # with open('src.py','w')as f:
    #     f.write(src)
    return src

opcode_class_list = ['bitwise','arithmetic','block','environment','comparison','keccak','system','memory','storage','log','stack','control_flow']
for opcode_class in opcode_class_list:
    src = get_src(opcode_class)
    func_list = get_funName('../src/ethereum/cancun/vm/instructions/' + opcode_class + '.py')
    generate_cfg(src,func_list,opcode_class)