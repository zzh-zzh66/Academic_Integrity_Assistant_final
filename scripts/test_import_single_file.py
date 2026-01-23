#!/usr/bin/env python3
"""
测试文件路径标记插入功能的覆盖率
"""
import os
import sys

# 添加项目根目录到 Python 路径
project_root = os.getenv("COZE_WORKSPACE_PATH")
if project_root:
    scripts_path = os.path.join(project_root, "scripts")
    if scripts_path not in sys.path:
        sys.path.insert(0, scripts_path)

from import_knowledge import insert_path_markers


def test_path_marker_coverage():
    """
    测试路径标记插入覆盖率
    目标：覆盖率 ≥ 80%
    """
    print("=" * 60)
    print("测试路径标记插入覆盖率")
    print("=" * 60)
    
    test_cases = [
        ("短文本", "test.txt", "这是一段短文本"),
        ("中等文本", "test.txt", "A" * 600),
        ("长文本", "test.txt", "这是一段很长的文本。" * 120),  # 约1200字
        ("超长文本", "test.txt", "这是一段超级长的文本用于测试覆盖率。" * 300),  # 约3000字
    ]
    
    all_passed = True
    
    for test_name, file_path, content in test_cases:
        print(f"\n📝 测试用例: {test_name}")
        print(f"   原始长度: {len(content)} 字符")
        
        result = insert_path_markers(content, file_path, interval=500)
        print(f"   结果长度: {len(result)} 字符")
        
        # 统计标记出现的次数
        marker = f"[文件路径: {file_path}]"
        marker_count = result.count(marker)
        print(f"   标记次数: {marker_count}")
        
        # 计算覆盖率：标记之间的距离不超过 interval * 1.2（允许20%的容错）
        if len(content) > 500:
            expected_markers = (len(content) // 500) + 1
            coverage = (marker_count / expected_markers) * 100
            print(f"   预期标记: {expected_markers}")
            print(f"   覆盖率: {coverage:.1f}%")
            
            if coverage >= 80:
                print(f"   ✅ 通过 (覆盖率 ≥ 80%)")
            else:
                print(f"   ❌ 失败 (覆盖率 < 80%)")
                all_passed = False
        else:
            print(f"   ℹ️  短文本，仅在开头添加标记")
        
        # 打印结果片段（前200字符）
        print(f"   结果片段: {result[:200]}...")
    
    print("\n" + "=" * 60)
    if all_passed:
        print("✅ 所有测试通过！")
        print("=" * 60)
        return True
    else:
        print("❌ 部分测试失败！")
        print("=" * 60)
        return False


def test_real_file():
    """
    使用真实文件进行测试
    """
    print("\n" + "=" * 60)
    print("使用真实文件测试")
    print("=" * 60)
    
    # 查找 assets/test 目录下的第一个文件
    test_dir = os.path.join(project_root, "assets/test")
    if not os.path.exists(test_dir):
        print(f"❌ 测试目录不存在: {test_dir}")
        return False
    
    from pathlib import Path
    test_files = list(Path(test_dir).rglob("*"))
    test_files = [f for f in test_files if f.is_file() and f.suffix.lower() not in [".doc"]]
    
    if not test_files:
        print(f"❌ 测试目录中没有文件")
        return False
    
    # 选择第一个文件进行测试
    test_file = test_files[0]
    relative_path = test_file.relative_to(Path(test_dir))
    
    print(f"\n📄 测试文件: {relative_path}")
    print(f"   完整路径: {test_file}")
    
    try:
        # 导入内容提取函数
        sys.path.insert(0, os.path.join(project_root, "src"))
        from utils.file.file import FileOps, File
        
        file_obj = File(url=str(test_file), file_type="document")
        content = FileOps.extract_text(file_obj)
        
        if not content:
            print(f"❌ 文件内容为空")
            return False
        
        print(f"   文件内容长度: {len(content)} 字符")
        
        # 插入路径标记
        result = insert_path_markers(content, str(relative_path), interval=500)
        
        # 统计标记
        marker = f"[文件路径: {relative_path}]"
        marker_count = result.count(marker)
        print(f"   插入标记次数: {marker_count}")
        
        if len(content) > 500:
            expected_markers = (len(content) // 500) + 1
            coverage = (marker_count / expected_markers) * 100
            print(f"   预期标记: {expected_markers}")
            print(f"   覆盖率: {coverage:.1f}%")
            
            if coverage >= 80:
                print(f"   ✅ 真实文件测试通过 (覆盖率 ≥ 80%)")
                return True
            else:
                print(f"   ❌ 真实文件测试失败 (覆盖率 < 80%)")
                return False
        else:
            print(f"   ℹ️  文件较短，仅在开头添加标记")
            return True
            
    except Exception as e:
        print(f"❌ 真实文件测试异常: {e}")
        return False


if __name__ == "__main__":
    # 运行单元测试
    unit_test_passed = test_path_marker_coverage()
    
    # 运行真实文件测试
    real_file_passed = test_real_file()
    
    # 总结
    print("\n" + "=" * 60)
    print("测试总结")
    print("=" * 60)
    print(f"单元测试: {'✅ 通过' if unit_test_passed else '❌ 失败'}")
    print(f"真实文件测试: {'✅ 通过' if real_file_passed else '❌ 失败'}")
    
    if unit_test_passed and real_file_passed:
        print("\n🎉 所有测试通过，可以执行知识库导入！")
        sys.exit(0)
    else:
        print("\n⚠️  部分测试失败，请检查代码！")
        sys.exit(1)
