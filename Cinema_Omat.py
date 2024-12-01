import c4d
import os
from c4d import gui

# Octane材质的类型ID
OCTANE_MATERIAL_TYPE_ID = 1029501  # 请替换为正确的Octane材质类型ID

# Octane材质类型的定义
OCTANE_MATERIAL_TYPES = {
    2510: "Diffuse",
    2511: "Glossy",
    2512: "Specular",
    2514: "Metallic",
    2516: "Universal"
}

def lerp_color(color1, color2, t):
    """Linearly interpolate between two colors."""
    return [int(color1[i] * (1 - t) + color2[i] * t) for i in range(3)]

def GradientToBitmap(gradient, width, height, gradient_type):
    bmp = c4d.bitmaps.BaseBitmap()
    if bmp is None:
        return None

    bmp.Init(width, height)

    knot_count = gradient.GetKnotCount()
    if knot_count == 0:
        return None

    knots = sorted([gradient.GetKnot(i) for i in range(knot_count)], key=lambda k: k["pos"])

    for x in range(width):
        for y in range(height):
            if gradient_type in [c4d.SLA_GRADIENT_TYPE_2D_U, c4d.SLA_GRADIENT_TYPE_2D_V]:
                t = float(x) if gradient_type == c4d.SLA_GRADIENT_TYPE_2D_U else float(y)
                t /= (width - 1)
            else:
                t = float(x) / (width - 1)

            if t <= knots[0]["pos"]:
                color = [int(knots[0]["col"][j] * 255) for j in range(3)]
            elif t >= knots[-1]["pos"]:
                color = [int(knots[-1]["col"][j] * 255) for j in range(3)]
            else:
                for i in range(knot_count - 1):
                    if knots[i]["pos"] <= t <= knots[i + 1]["pos"]:
                        lerp_factor = (t - knots[i]["pos"]) / (knots[i + 1]["pos"] - knots[i]["pos"])
                        color = lerp_color(
                            [knots[i]["col"][j] * 255 for j in range(3)],
                            [knots[i + 1]["col"][j] * 255 for j in range(3)],
                            lerp_factor
                        )
                        break

            bmp.SetPixel(x, y, *color)

    return bmp

def save_gradient_image(gradient, obj_name, material_name, channel_name):
    bmp = GradientToBitmap(gradient, 256, 256, c4d.SLA_GRADIENT_TYPE_2D_U)  # 假设为2D_U类型渐变
    if bmp is None:
        return None

    # 替换材质名称中的 '.'
    material_name = material_name.replace('.', '_')

    filename = f"{obj_name}_{material_name}_{channel_name}_gradient.jpg"
    output_path = os.path.join(os.path.expanduser('~/Documents'), filename)
    bmp.Save(output_path, c4d.FILTER_JPG)
    print(f"Saved gradient image to: {output_path}")
    return output_path

def GetShaderInfo(shader, obj_name, material_name, channel_name):
    """
    获取节点信息的函数
    """
    if not shader:
        return "No shader found."

    shader_info = []

    shader_name = shader.GetName()
    shader_type = shader.GetType()
    shader_info.append("Shader Name: {}".format(shader_name))
    shader_info.append("Shader Type: {}".format(shader_type))

    if shader_type == 1011100:  # 渐变
        gradient = shader[c4d.SLA_GRADIENT_GRADIENT]
        shader_info.append("Gradient: {}".format(gradient))
        gradient_path = save_gradient_image(gradient, obj_name, material_name, channel_name)
        if gradient_path:
            shader_info.append(f"Gradient Image Path: {gradient_path}")

    elif shader_type == 5832:  # 颜色
        color = shader[c4d.COLORSHADER_COLOR]
        shader_info.append("Color: Vector({}, {}, {})".format(color.x, color.y, color.z))

    elif shader_type == 1029508:  # ImageTexture
        image_path = shader[c4d.IMAGETEXTURE_FILE]
        shader_info.append("Image Texture File: {}".format(image_path))
    
    elif shader_type == 1029506:  # FloatTexture
        float_value = shader[c4d.FLOATTEXTURE_VALUE]
        shader_info.append("Float Texture Value: {}".format(float_value))    
        
    elif shader_type == 1029504:  # RgbSpectrum
        rgb_color = shader[c4d.RGBSPECTRUMSHADER_COLOR]
        shader_info.append("RGB Spectrum Color: Vector({}, {}, {})".format(rgb_color.x, rgb_color.y, rgb_color.z))    

    # 检查是否为BitmapShader以获取文件名
    if shader_type == c4d.Xbitmap:
        file_path = shader[c4d.BITMAPSHADER_FILENAME]
        shader_info.append("Bitmap Shader File: {}".format(file_path))

    # 检查是否为ColorCorrection类型
    if shader_name == "ColorCorrection":
        shader_info.append("Shader is a Color Correction Node.")
        # 获取Color Correction的链接
        link_shader = shader[c4d.COLORCOR_TEXTURE_LNK]
        if isinstance(link_shader, c4d.BaseShader):
            shader_info.append("Color Correction Link: {}".format(link_shader))
            # 递归获取链接的Shader信息
            linked_shader_info = GetShaderInfo(link_shader, obj_name, material_name, "ColorCorrection_Link")
            shader_info.append(linked_shader_info)

    # 每个通道信息结束后添加分割符
    shader_info.append("#####")

    return "\n".join(shader_info)

def GetTextureTagInfo(tag):
    """
    获取TextureTag信息的函数
    """
    tag_info = []

    material = tag.GetMaterial()
    if material:
        # 替换材质名称中的 '.'
        material_name = material.GetName().replace('.', '_')
        tag_info.append("Material: {}".format(material_name))

    tag_info.append("Texture Projection Matrix: {}".format(tag.GetMl()))
    tag_info.append("Texture Position: {}".format(tag.GetPos()))
    tag_info.append("Texture Rotation: {}".format(tag.GetRot()))
    tag_info.append("Texture Scale: {}".format(tag.GetScale()))

    tag_info.append("#####")

    return "\n".join(tag_info)

def GenerateUniqueMaterialName(material_name, used_names):
    """
    生成唯一的材质名称，并将名称中的 '.' 替换为 '_'
    """
    # 替换材质名称中的 '.'
    material_name = material_name.replace('.', '_')

    if material_name not in used_names:
        used_names.add(material_name)
        return material_name

    # 如果已经存在相同名称的材质，则在名称后添加后缀
    index = 0
    unique_name = f"{material_name}_{index}"
    while unique_name in used_names:
        index += 1
        unique_name = f"{material_name}_{index}"

    used_names.add(unique_name)
    return unique_name

def GetOctaneMaterialInfo(material, obj_name, used_names):
    """
    获取Octane材质信息的函数, 并处理发光（Emission）信息以及其他着色器链接
    """
    if not material:
        return "No material found."

    # 生成唯一的材质名称，并替换 '.'
    original_name = material.GetName()
    unique_material_name = GenerateUniqueMaterialName(original_name, used_names)

    material_info = []

    material_info.append("Object Name: {}".format(obj_name))
    material_info.append("Parent Name: {}".format(material.GetUp().GetName() if material.GetUp() else "None"))

    material_info.append("Material Name: {}".format(unique_material_name))

    mat_type = material[c4d.OCT_MATERIAL_TYPE]
    material_type_name = OCTANE_MATERIAL_TYPES.get(mat_type, "Unknown")
    material_info.append("Type: {} ({})".format(mat_type, material_type_name))

    # Check if emission is enabled
    use_emission = material[c4d.OCT_MAT_USE_EMISSION]
    material_info.append("Use Emission: {}".format(use_emission))

    if use_emission:
        emission_shader = material[c4d.OCT_MATERIAL_EMISSION]
        if isinstance(emission_shader, c4d.BaseShader):
            material_info.append("Emission Shader: {}".format(emission_shader.GetName()))
            
            # Handle Blackbody or Texture emission
            if emission_shader.GetType() == 1029641:  # Blackbody Emission
                material_info.append("Emission Type: Blackbody")
                efficiency_or_tex = emission_shader[c4d.BBEMISSION_EFFIC_OR_TEX]
                material_info.append("Blackbody Emission Efficiency or Texture: {}".format(efficiency_or_tex))

                # Check for linked shader in Blackbody Emission
                if isinstance(efficiency_or_tex, c4d.BaseShader):
                    material_info.append("Blackbody Emission linked Shader: {}".format(efficiency_or_tex.GetName()))
                    shader_info = GetShaderInfo(efficiency_or_tex, obj_name, unique_material_name, "Blackbody_Emission")
                    material_info.append(shader_info)

            elif emission_shader.GetType() == 1029642:  # Texture Emission
                material_info.append("Emission Type: Texture")
                efficiency_or_tex = emission_shader[c4d.TEXEMISSION_EFFIC_OR_TEX]
                material_info.append("Texture Emission Efficiency or Texture: {}".format(efficiency_or_tex))

                # Check for linked shader in Texture Emission
                if isinstance(efficiency_or_tex, c4d.BaseShader):
                    material_info.append("Texture Emission linked Shader: {}".format(efficiency_or_tex.GetName()))
                    shader_info = GetShaderInfo(efficiency_or_tex, obj_name, unique_material_name, "Texture_Emission")
                    material_info.append(shader_info)

    # 获取并打印Octane材质的更多信息
    material_info.append("Use Color: {}".format(material[c4d.OCT_MAT_USE_COLOR]))

    # 检查 Diffuse Link
    diffuse_link = material[c4d.OCT_MATERIAL_DIFFUSE_LINK]
    if isinstance(diffuse_link, c4d.BaseShader):
        material_info.append("Diffuse Link: {}".format(diffuse_link))
        shader_info = GetShaderInfo(diffuse_link, obj_name, unique_material_name, "Diffuse")
        material_info.append(shader_info)

        # 优先使用链接的颜色或其他信息
        if diffuse_link.GetType() == 5832:  # 颜色
            color = diffuse_link[c4d.COLORSHADER_COLOR]
            material_info.append("Diffuse Color (Link): Vector({}, {}, {})".format(color.x, color.y, color.z))
        elif diffuse_link.GetType() == 1011100:  # 渐变
            gradient = diffuse_link[c4d.SLA_GRADIENT_GRADIENT]
            material_info.append("Diffuse Gradient (Link): {}".format(gradient))
            gradient_path = save_gradient_image(gradient, obj_name, unique_material_name, "Diffuse_Gradient")
            if gradient_path:
                material_info.append(f"Gradient Image Path: {gradient_path}")
        elif diffuse_link.GetType() == 1029508:  # ImageTexture
            image_path = diffuse_link[c4d.IMAGETEXTURE_FILE]
            material_info.append("Diffuse Image Texture (Link): {}".format(image_path))
    else:
        diffuse_color = material[c4d.OCT_MATERIAL_DIFFUSE_COLOR]
        if isinstance(diffuse_color, c4d.Vector):
            material_info.append("Diffuse Color: Vector({}, {}, {})".format(diffuse_color.x, diffuse_color.y, diffuse_color.z))
    material_info.append("Diffuse Float: {}".format(material[c4d.OCT_MATERIAL_DIFFUSE_FLOAT]))

    material_info.append("#####")  # 添加分割符

    material_info.append("Use Roughness: {}".format(material[c4d.OCT_MAT_USE_ROUGHNESS]))

    roughness_color = material[c4d.OCT_MATERIAL_ROUGHNESS_COLOR]
    if isinstance(roughness_color, c4d.Vector):
        material_info.append("Roughness Color: Vector({}, {}, {})".format(roughness_color.x, roughness_color.y, roughness_color.z))
    material_info.append("Roughness Float: {}".format(material[c4d.OCT_MATERIAL_ROUGHNESS_FLOAT]))
    material_info.append("Roughness Link: {}".format(material[c4d.OCT_MATERIAL_ROUGHNESS_LINK]))

    roughness_link = material[c4d.OCT_MATERIAL_ROUGHNESS_LINK]
    if isinstance(roughness_link, c4d.BaseShader):
        material_info.append(GetShaderInfo(roughness_link, obj_name, unique_material_name, "Roughness"))

    material_info.append("#####")  # 添加分割符

    bump_link = material[c4d.OCT_MATERIAL_BUMP_LINK]
    if isinstance(bump_link, c4d.BaseShader):
        material_info.append("Bump Link: {}".format(bump_link))
        material_info.append(GetShaderInfo(bump_link, obj_name, unique_material_name, "Bump"))

    material_info.append("Use Bump: {}".format(material[c4d.OCT_MAT_USE_BUMP]))

    material_info.append("#####")  # 添加分割符

    material_info.append("Use Normal: {}".format(material[c4d.OCT_MAT_USE_NORMAL]))
    normal_link = material[c4d.OCT_MATERIAL_NORMAL_LINK]
    if isinstance(normal_link, c4d.BaseShader):
        material_info.append("Normal Link: {}".format(normal_link))
        material_info.append(GetShaderInfo(normal_link, obj_name, unique_material_name, "Normal"))

    material_info.append("#####")  # 添加分割符

    material_info.append("Use Displacement: {}".format(material[c4d.OCT_MAT_USE_DISPLACEMENT]))

    material_info.append("#####")  # 添加分割符

    material_info.append("Use Opacity: {}".format(material[c4d.OCT_MAT_USE_OPACITY]))
    opacity_link = material[c4d.OCT_MATERIAL_OPACITY_LINK]
    if isinstance(opacity_link, c4d.BaseShader):
        material_info.append("Opacity Link: {}".format(opacity_link))
        material_info.append(GetShaderInfo(opacity_link, obj_name, unique_material_name, "Opacity"))

    opacity_color = material[c4d.OCT_MATERIAL_OPACITY_COLOR]
    if isinstance(opacity_color, c4d.Vector):
        material_info.append("Opacity Color: Vector({}, {}, {})".format(opacity_color.x, opacity_color.y, opacity_color.z))
    material_info.append("Opacity Float: {}".format(material[c4d.OCT_MATERIAL_OPACITY_FLOAT]))

    material_info.append("#####")  # 添加分割符

    material_info.append("Use Transmission: {}".format(material[c4d.OCT_MAT_USE_TRANSMISSION]))

    transmission_color = material[c4d.OCT_MATERIAL_TRANSMISSION_COLOR]
    if isinstance(transmission_color, c4d.Vector):
        material_info.append("Transmission Color: Vector({}, {}, {})".format(transmission_color.x, transmission_color.y, transmission_color.z))
    material_info.append("Transmission Float: {}".format(material[c4d.OCT_MATERIAL_TRANSMISSION_FLOAT]))
    transmission_link = material[c4d.OCT_MATERIAL_TRANSMISSION_LINK]
    if isinstance(transmission_link, c4d.BaseShader):
        material_info.append("Transmission Link: {}".format(transmission_link))
        material_info.append(GetShaderInfo(transmission_link, obj_name, unique_material_name, "Transmission"))

    material_info.append("#####")  # 添加分割符

    material_info.append("Emission: {}".format(material[c4d.OCT_MATERIAL_EMISSION]))

    # Universal材质类型的特定信息
    if mat_type == 2516:  # Universal类型
        material_info.append("Specular Map Float: {}".format(material[c4d.OCT_MAT_SPECULAR_MAP_FLOAT]))
        material_info.append("Specular Float: {}".format(material[c4d.OCT_MATERIAL_SPECULAR_FLOAT]))
        material_info.append("Parameter 2639: {}".format(material[2639]))  # 假设2639是一个颜色向量
        material_info.append("Index: {}".format(material[c4d.OCT_MATERIAL_INDEX]))

    material_info.append("#####")  # 添加分割符

    return "\n".join(material_info)

def main():
    doc = c4d.documents.GetActiveDocument()
    selected_objects = doc.GetActiveObjects(c4d.GETACTIVEOBJECTFLAGS_CHILDREN)

    if not selected_objects:
        gui.MessageDialog("No objects selected.")
        return

    output_lines = []  # 用于存储输出信息的列表
    used_names = set()  # 用于存储已使用的材质名称

    for obj in selected_objects:
        mat_tags = [tag for tag in obj.GetTags() if isinstance(tag, c4d.TextureTag)]

        if not mat_tags:
            output_lines.append("No material tags found on object: {}".format(obj.GetName()))
            continue

        for tag in mat_tags:
            material = tag.GetMaterial()
            if material and material.GetType() == OCTANE_MATERIAL_TYPE_ID:
                texture_tag_info = GetTextureTagInfo(tag)
                output_lines.append(texture_tag_info)

                material_info = GetOctaneMaterialInfo(material, obj.GetName(), used_names)
                output_lines.append(material_info)
            else:
                output_lines.append("No Octane material found on tag: {}".format(tag.GetName()))

    # 将输出信息写入文本文件
    output_path = os.path.join(os.path.expanduser('~/Documents'), "octane_material_info.txt")
    with open(output_path, "w", encoding="utf-8") as file:
        file.write("\n".join(output_lines))

if __name__ == '__main__':
    main()
