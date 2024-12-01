import bpy
import os
import re


bl_info = {
    "name": "Import Octane Material",
    "blender": (4, 2, 0),
    "category": "Import-Export",
    "author": "475519905",
    "version": (1, 0, 1),
    "description": "Imports and applies Octane materials directly into Blender materials panel.",
    
}


def parse_vector(vector_str):
    cleaned = re.sub(r'[^\d.-]', ' ', vector_str)
    return [float(x) for x in cleaned.split()]

def parse_material_info(file_path):
    """解析材质信息文件，返回材质属性字典。"""
    materials = {}
    current_material = None
    current_shader = None
    color_correction_skip = False  # 跳过标志

    with open(file_path, 'r', encoding='utf-8') as file:
        lines = file.readlines()
        i = 0
        while i < len(lines):
            line = lines[i].strip()

            # 匹配Material行
            if line.startswith("Material Name:"):
                current_material = line.split(":", 1)[1].strip()
                materials[current_material] = {}
                current_shader = None
                color_correction_skip = False
            elif current_material:
                if ": " in line:
                    key, value = line.split(":", 1)
                    key = key.strip()
                    value = value.strip()

                    if 'Link' in key:
                        current_shader = key.split()[0]
                        materials[current_material][key] = value
                    elif current_shader and (key.startswith('Shader Name') or key.startswith('Shader Type') or key.startswith('Image Texture') or key.startswith('Gradient') or key.startswith('Color')):
                        materials[current_material][f"{current_shader} {key}"] = value
                    else:
                        materials[current_material][key] = value

                    # 检查ColorCorrection节点，如果匹配则向下跳4行获取ImageTexture、颜色或向下跳9行获取渐变信息
                    if line.startswith("Shader Name: ColorCorrection"):
                        color_correction_skip = True
                        i += 4  # 跳过4行获取ImageTexture或颜色信息
                        texture_line = lines[i].strip()

                        # 如果存在ImageTexture节点
                        if texture_line.startswith("Image Texture File:"):
                            image_texture_file = texture_line.split(":", 1)[1].strip()
                            materials[current_material][f"{current_shader} Image Texture File"] = image_texture_file
                        # 否则尝试解析颜色信息
                        elif texture_line.startswith("Color:"):
                            color_value = texture_line.split(":", 1)[1].strip()
                            materials[current_material][f"{current_shader} Color (Link)"] = color_value
                        # 如果存在渐变，则向下跳9行
                        elif texture_line.startswith("Gradient:"):
                            i += 9  # 跳过9行获取渐变信息
                            gradient_value_line = lines[i].strip()
                            if gradient_value_line.startswith("Gradient Image Path:"):
                                gradient_path = gradient_value_line.split(":", 1)[1].strip()
                                materials[current_material][f"{current_shader} Gradient Image Path"] = gradient_path

                        color_correction_skip = False
                        i += 1  # 移动到下一个有效行继续解析
                        continue

                elif color_correction_skip:
                    # 检查当前行是否包含ImageTexture、颜色或渐变的文件路径
                    if line.startswith("Image Texture File:"):
                        materials[current_material][f"{current_shader} Image Texture File"] = line.split(":", 1)[1].strip()
                    elif line.startswith("Color:"):
                        materials[current_material][f"{current_shader} Color (Link)"] = line.split(":", 1)[1].strip()
                    elif line.startswith("Gradient Image Path:"):
                        materials[current_material][f"{current_shader} Gradient Image Path"] = line.split(":", 1)[1].strip()
                    color_correction_skip = False

            i += 1

    return materials

def create_texture_node(nodes, links, principled, input_name, image_path):
    tex_node = nodes.new(type='ShaderNodeTexImage')
    tex_node.location = (-300, len(nodes) * -300)
    
    if os.path.exists(image_path):
        img = bpy.data.images.load(image_path)
        tex_node.image = img
    else:
        print(f"Warning: Image file not found: {image_path}")
    
    if input_name == 'Normal':
        normal_map = nodes.new(type='ShaderNodeNormalMap')
        normal_map.location = (-150, len(nodes) * -300)
        links.new(tex_node.outputs['Color'], normal_map.inputs['Color'])
        links.new(normal_map.outputs['Normal'], principled.inputs['Normal'])
    elif input_name == 'Bump':
        bump_node = nodes.new(type='ShaderNodeBump')
        bump_node.location = (-150, len(nodes) * -300)
        links.new(tex_node.outputs['Color'], bump_node.inputs['Height'])
        links.new(bump_node.outputs['Normal'], principled.inputs['Normal'])
    else:
        if input_name in principled.inputs:
            links.new(tex_node.outputs['Color'], principled.inputs[input_name])
        else:
            print(f"Warning: Input '{input_name}' not found in Principled BSDF")
    
    return tex_node

def set_principled_input(principled, input_name, value):
    if input_name in principled.inputs:
        socket = principled.inputs[input_name]
        if socket.type == 'RGBA':
            if isinstance(value, (list, tuple)) and len(value) >= 3:
                socket.default_value = (*value[:3], 1)  # 确保是4元素的颜色值
            elif isinstance(value, (int, float)):
                socket.default_value = (value, value, value, 1)
        elif socket.type in ['VALUE', 'VECTOR']:
            if isinstance(value, (int, float)):
                socket.default_value = value
            elif isinstance(value, (list, tuple)):
                socket.default_value = value[0] if len(value) > 0 else 0.0
    else:
        print(f"Warning: Input '{input_name}' not found in Principled BSDF")

def apply_material_properties(materials, base_path):
    for mat_name, properties in materials.items():
        if mat_name in bpy.data.materials:
            mat = bpy.data.materials[mat_name]
        else:
            mat = bpy.data.materials.new(name=mat_name)
        
        mat.use_nodes = True
        nodes = mat.node_tree.nodes
        links = mat.node_tree.links
        
        nodes.clear()
        
        principled = nodes.new(type='ShaderNodeBsdfPrincipled')
        principled.location = (0, 0)
        
        output = nodes.new(type='ShaderNodeOutputMaterial')
        output.location = (300, 0)
        
        links.new(principled.outputs['BSDF'], output.inputs['Surface'])
        
        material_type = properties.get('Type', '').lower()
        is_specular = 'specular' in material_type

        channel_mapping = {
            'Diffuse': 'Base Color',
            'Roughness': 'Roughness',
            'Normal': 'Normal',
            'Bump': 'Normal',
            'Displacement': 'Displacement',
            'Opacity': 'Alpha',
            'Metalness': 'Metallic',
            'Emission': 'Emission',
            'Transmission': 'Transmission'
        }

        for prop, input_name in channel_mapping.items():
            link_key = f'{prop} Link'
            color_key = f'{prop} Color'
            float_key = f'{prop} Float'
            
            # 首先检查是否有图像纹理
            image_texture_file = properties.get(f'{prop} Image Texture File')
            if image_texture_file:
                create_texture_node(nodes, links, principled, input_name, image_texture_file)
                continue  # 如果使用了图像纹理，跳过后续的颜色和float处理

            # 检查Link中的着色器
            if link_key in properties:
                shader_name = properties.get(f'{prop} Shader Name', '').lower()
                if '渐变' in shader_name:
                    gradient_path = properties.get(f'{prop} Gradient Image Path')
                    if gradient_path:
                        create_texture_node(nodes, links, principled, input_name, gradient_path)
                elif '颜色' in shader_name or 'color' in shader_name:
                    color_value = properties.get(f'{prop} Color (Link)')
                    if color_value:
                        color = parse_vector(color_value)
                        set_principled_input(principled, input_name, color)
            # 如果没有Link或Link中没有相关着色器，则检查Color和Float
            elif color_key in properties:
                color = parse_vector(properties[color_key])
                if color == [0, 0, 0] and float_key in properties:
                    set_principled_input(principled, input_name, float(properties[float_key]))
                else:
                    set_principled_input(principled, input_name, color)
            elif float_key in properties:
                set_principled_input(principled, input_name, float(properties[float_key]))
            else:
                print(f"Info: No data found for {prop} channel")

        # 特殊处理Transmission
        if is_specular:
            principled.inputs[17].default_value = 1.0
        elif 'Transmission Float' in properties:
            set_principled_input(principled, 'Transmission', float(properties['Transmission Float']))

        # 设置混合模式
        if 'Opacity Float' in properties or 'Opacity Color' in properties:
            mat.blend_method = 'HASHED'
            mat.shadow_method = 'HASHED'

        print(f"Material '{mat_name}' processed")

def main():
    input_file_path = os.path.join(os.path.expanduser('~'), 'Documents', 'chche', 'octane_material_info.txt')
    
    if not os.path.exists(input_file_path):
        print(f"File not found: {input_file_path}")
        return

    materials_info = parse_material_info(input_file_path)
    base_path = os.path.dirname(input_file_path)
    apply_material_properties(materials_info, base_path)

    print("Materials have been updated in Blender.")

class IMPORT_OT_OctaneMaterial(bpy.types.Operator):
    bl_idname = "import_octane_material.import"
    bl_label = "Import Octane Material"
    bl_description = "Import materials from Octane"

    def execute(self, context):
        main()
        return {'FINISHED'}

class IMPORT_PT_OctaneMaterialPanel(bpy.types.Panel):
    bl_label = "Import Octane Material"
    bl_idname = "IMPORT_PT_OctaneMaterialPanel"
    bl_space_type = 'VIEW_3D'
    bl_region_type = 'UI'
    bl_category = "Material"

    def draw(self, context):
        layout = self.layout
        layout.operator("import_octane_material.import")

def register():
    bpy.utils.register_class(IMPORT_OT_OctaneMaterial)
    bpy.utils.register_class(IMPORT_PT_OctaneMaterialPanel)

def unregister():
    bpy.utils.unregister_class(IMPORT_OT_OctaneMaterial)
    bpy.utils.unregister_class(IMPORT_PT_OctaneMaterialPanel)

if __name__ == "__main__":
    register()
