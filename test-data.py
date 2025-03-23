"""
直接使用已有的应用和模型插入测试数据
"""
from app import app, db, Category, Product, Supplier, Order, OrderItem
from datetime import datetime, timedelta
import random
import string

def generate_order_number():
    """生成随机订单号"""
    prefix = "ORD"
    date_part = datetime.now().strftime("%Y%m%d")
    random_part = ''.join(random.choices(string.ascii_uppercase + string.digits, k=5))
    return f"{prefix}-{date_part}-{random_part}"

def insert_test_data():
    """插入测试数据到数据库，带有重复检查"""
    with app.app_context():
        # 1. 添加类别数据（检查是否已存在）
        category_data = [
            {'name': '电子产品', 'description': '各类电子设备和配件'},
            {'name': '办公用品', 'description': '办公所需的各类用品'},
            {'name': '家居用品', 'description': '家庭生活所需的各类物品'},
            {'name': '食品饮料', 'description': '各类食品和饮料'},
            {'name': '服装鞋帽', 'description': '各类服装和鞋帽'}
        ]
        
        categories = []
        for cat_dict in category_data:
            # 检查类别是否已存在
            existing = Category.query.filter_by(name=cat_dict['name']).first()
            if not existing:
                category = Category(**cat_dict)
                db.session.add(category)
                categories.append(category)
                print(f"添加新类别: {cat_dict['name']}")
            else:
                categories.append(existing)
                print(f"类别已存在: {cat_dict['name']}")
                
        db.session.commit()
        print("类别数据处理完成")

        # 获取所有类别，确保我们有正确的ID
        all_categories = Category.query.all()
        category_map = {c.name: c for c in all_categories}

        # 2. 添加供应商数据（检查是否已存在）
        supplier_data = [
            {'name': '环球电子有限公司', 'contact_person': '张三', 'email': 'zhangsan@example.com', 
             'phone': '13800138001', 'address': '北京市海淀区中关村南大街5号'},
            {'name': '办公伙伴贸易有限公司', 'contact_person': '李四', 'email': 'lisi@example.com', 
             'phone': '13900139002', 'address': '上海市浦东新区张江高科技园区'},
            {'name': '优品家居用品公司', 'contact_person': '王五', 'email': 'wangwu@example.com', 
             'phone': '13700137003', 'address': '广州市天河区天河路385号'},
            {'name': '美味食品配送中心', 'contact_person': '赵六', 'email': 'zhaoliu@example.com', 
             'phone': '13600136004', 'address': '深圳市南山区科技园'},
            {'name': '时尚服饰有限公司', 'contact_person': '钱七', 'email': 'qianqi@example.com', 
             'phone': '13500135005', 'address': '杭州市西湖区文三路'}
        ]
        
        for sup_dict in supplier_data:
            # 检查供应商是否已存在
            existing = Supplier.query.filter_by(name=sup_dict['name']).first()
            if not existing:
                supplier = Supplier(**sup_dict)
                db.session.add(supplier)
                print(f"添加新供应商: {sup_dict['name']}")
        
        db.session.commit()
        print("供应商数据处理完成")

        # 3. 添加产品数据（检查是否已存在）
        product_data = [
            # 电子产品
            {'name': '笔记本电脑', 'description': '高性能商务办公笔记本', 'price': 5999.00, 'stock': 50, 
             'category_id': category_map['电子产品'].id if '电子产品' in category_map else 1},
            {'name': '智能手机', 'description': '新一代5G智能手机', 'price': 3999.00, 'stock': 100, 
             'category_id': category_map['电子产品'].id if '电子产品' in category_map else 1},
            {'name': '蓝牙耳机', 'description': '无线蓝牙降噪耳机', 'price': 899.00, 'stock': 200, 
             'category_id': category_map['电子产品'].id if '电子产品' in category_map else 1},
            {'name': '平板电脑', 'description': '10.2英寸高清显示屏平板', 'price': 2999.00, 'stock': 80, 
             'category_id': category_map['电子产品'].id if '电子产品' in category_map else 1},
            {'name': '智能手表', 'description': '健康监测智能手表', 'price': 1599.00, 'stock': 120, 
             'category_id': category_map['电子产品'].id if '电子产品' in category_map else 1},
            
            # 办公用品
            {'name': '打印机', 'description': '彩色激光多功能一体机', 'price': 1899.00, 'stock': 30, 
             'category_id': category_map['办公用品'].id if '办公用品' in category_map else 2},
            {'name': '签字笔', 'description': '0.5mm黑色水性签字笔', 'price': 3.50, 'stock': 1000, 
             'category_id': category_map['办公用品'].id if '办公用品' in category_map else 2},
            {'name': '订书机', 'description': '重型订书机可订50页', 'price': 35.00, 'stock': 200, 
             'category_id': category_map['办公用品'].id if '办公用品' in category_map else 2},
            {'name': 'A4纸', 'description': '80g A4复印纸 500张/包', 'price': 25.00, 'stock': 500, 
             'category_id': category_map['办公用品'].id if '办公用品' in category_map else 2},
            {'name': '文件夹', 'description': 'A4文件夹资料册', 'price': 8.80, 'stock': 800, 
             'category_id': category_map['办公用品'].id if '办公用品' in category_map else 2},
            
            # 家居用品
            {'name': '电饭煲', 'description': '4L智能电饭煲', 'price': 299.00, 'stock': 100, 
             'category_id': category_map['家居用品'].id if '家居用品' in category_map else 3},
            {'name': '床上四件套', 'description': '纯棉床上用品四件套', 'price': 299.00, 'stock': 50, 
             'category_id': category_map['家居用品'].id if '家居用品' in category_map else 3},
            {'name': '吸尘器', 'description': '无线手持吸尘器', 'price': 1299.00, 'stock': 60, 
             'category_id': category_map['家居用品'].id if '家居用品' in category_map else 3},
            {'name': '台灯', 'description': 'LED护眼台灯', 'price': 129.00, 'stock': 150, 
             'category_id': category_map['家居用品'].id if '家居用品' in category_map else 3},
            {'name': '毛巾', 'description': '纯棉吸水毛巾', 'price': 29.90, 'stock': 300, 
             'category_id': category_map['家居用品'].id if '家居用品' in category_map else 3},
            
            # 食品饮料
            {'name': '矿泉水', 'description': '550ml*24瓶装纯净水', 'price': 32.00, 'stock': 200, 
             'category_id': category_map['食品饮料'].id if '食品饮料' in category_map else 4},
            {'name': '巧克力', 'description': '100g黑巧克力', 'price': 15.80, 'stock': 400, 
             'category_id': category_map['食品饮料'].id if '食品饮料' in category_map else 4},
            {'name': '咖啡', 'description': '速溶黑咖啡粉100g', 'price': 35.00, 'stock': 150, 
             'category_id': category_map['食品饮料'].id if '食品饮料' in category_map else 4},
            {'name': '坚果礼盒', 'description': '混合坚果礼盒装300g', 'price': 69.90, 'stock': 100, 
             'category_id': category_map['食品饮料'].id if '食品饮料' in category_map else 4},
            {'name': '蜂蜜', 'description': '纯天然蜂蜜500g', 'price': 85.00, 'stock': 80, 
             'category_id': category_map['食品饮料'].id if '食品饮料' in category_map else 4},
            
            # 服装鞋帽
            {'name': 'T恤', 'description': '纯棉圆领短袖T恤', 'price': 99.00, 'stock': 300, 
             'category_id': category_map['服装鞋帽'].id if '服装鞋帽' in category_map else 5},
            {'name': '牛仔裤', 'description': '直筒修身牛仔裤', 'price': 199.00, 'stock': 200, 
             'category_id': category_map['服装鞋帽'].id if '服装鞋帽' in category_map else 5},
            {'name': '运动鞋', 'description': '轻便透气运动跑鞋', 'price': 329.00, 'stock': 150, 
             'category_id': category_map['服装鞋帽'].id if '服装鞋帽' in category_map else 5},
            {'name': '连衣裙', 'description': '夏季碎花连衣裙', 'price': 239.00, 'stock': 100, 
             'category_id': category_map['服装鞋帽'].id if '服装鞋帽' in category_map else 5},
            {'name': '棒球帽', 'description': '纯棉遮阳棒球帽', 'price': 49.90, 'stock': 200, 
             'category_id': category_map['服装鞋帽'].id if '服装鞋帽' in category_map else 5}
        ]
        
        for prod_dict in product_data:
            # 检查产品是否已存在
            existing = Product.query.filter_by(name=prod_dict['name']).first()
            if not existing:
                product = Product(**prod_dict)
                db.session.add(product)
                print(f"添加新产品: {prod_dict['name']}")
            else:
                print(f"产品已存在: {prod_dict['name']}")
        
        db.session.commit()
        print("产品数据处理完成")

        # 4. 添加订单和订单项数据（订单号有唯一约束，所以不检查重复）
        # 首先检查是否已有订单
        if Order.query.count() >= 10:
            print("已有足够的订单数据，跳过订单添加")
        else:
            # 获取所有产品ID
            all_products = Product.query.all()
            
            # 创建10个不同日期的订单
            for i in range(10):
                order_date = datetime.now() - timedelta(days=i*3)
                status = random.choice(['pending', 'completed', 'cancelled'])
                
                order = Order(
                    order_number=generate_order_number(),
                    order_date=order_date,
                    status=status,
                    notes=f"测试订单 #{i+1}"
                )
                db.session.add(order)
                db.session.flush()  # 获取订单ID
                
                # 每个订单随机添加2-5个订单项
                order_items_count = random.randint(2, 5)
                selected_products = random.sample(all_products, min(order_items_count, len(all_products)))
                
                total_amount = 0
                for product in selected_products:
                    quantity = random.randint(1, 5)
                    price = product.price
                    
                    order_item = OrderItem(
                        order_id=order.id,
                        product_id=product.id,
                        quantity=quantity,
                        price=price
                    )
                    
                    total_amount += price * quantity
                    db.session.add(order_item)
                
                # 更新订单总金额
                order.total_amount = total_amount
                print(f"添加新订单: {order.order_number}, 商品数: {len(selected_products)}")
            
            db.session.commit()
            print("订单和订单项数据处理完成")
        
        print("所有测试数据添加完成!")

if __name__ == "__main__":
    insert_test_data()