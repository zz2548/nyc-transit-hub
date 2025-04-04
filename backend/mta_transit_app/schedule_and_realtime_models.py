from sqlalchemy import create_engine, Column, Integer, String, Float, Boolean, ForeignKey, Time, CheckConstraint
from sqlalchemy.orm import declarative_base, relationship, sessionmaker
from google.transit import gtfs_realtime_pb2
import requests
import os

BASE_DIR = os.path.dirname(os.path.abspath(__file__))  # 获取脚本所在目录
db_path = os.path.join(BASE_DIR, "instance", "gtfs.db")  # 组合数据库路径

# 创建数据库连接
DATABASE_URL = f"sqlite:///{db_path}"  # 生成 SQLite URL
engine = create_engine(DATABASE_URL, echo=True)  # echo=True 显示 SQL 语句
Base = declarative_base()
SessionLocal = sessionmaker(bind=engine)

class agency(Base):
    __tablename__ = 'agency'
    agency_id = Column(String, primary_key= True)
    agency_name = Column(String, nullable=False)
    agency_url = Column(String, nullable=False)
    agency_timezone = Column(String, nullable=False)
    agency_lang = Column(String)
    agency_phone = Column(String)

class stops(Base):
    __tablename__ = 'stops'
    stop_id = Column(String, primary_key= True)
    stop_name = Column(String)
    stop_lat = Column(Float)
    stop_lon = Column(Float)
    location_type = Column(Integer)
    parent_station = Column(String, ForeignKey('stops.stop_id'))

    parent = relationship('stops', remote_side=[stop_id])

class routes(Base):
    __tablename__ = 'routes'
    route_id = Column(String, primary_key= True)
    agency_id = Column(String, ForeignKey('agency.agency_id'))
    route_short_name = Column(String)
    route_long_name = Column(String)
    route_desc = Column(String)
    route_type = Column(Integer)
    route_url = Column(String)
    route_color = Column(String)
    route_text_color = Column(String)

    agency = relationship('agency')

class trips(Base):
    __tablename__ = 'trips'
    route_id = Column(String, ForeignKey('routes.route_id'), nullable=False)
    service_id = Column(String, ForeignKey('calendar.service_id'), nullable=False)
    trip_id = Column(String, primary_key=True)
    trip_headsign = Column(String)
    direction_id = Column(Integer)
    shape_id = Column(String, ForeignKey('shapes.shape_id'))

class stop_times(Base):
    __tablename__ = 'stop_times'
    trip_id	= Column(String, ForeignKey('trips.trip_id'), nullable=False)
    stop_id	= Column(String)
    arrival_time = Column(Time)
    departure_time = Column(Time)
    stop_sequence = Column(Integer, primary_key=True)

class calendar(Base):
    __tablename__ = 'calendar'
    service_id = Column(String, primary_key=True)
    monday = Column(Integer, nullable=False)
    tuesday = Column(Integer, nullable=False)
    wednesday = Column(Integer, nullable=False)
    thursday = Column(Integer, nullable=False)
    friday = Column(Integer, nullable=False)
    saturday = Column(Integer, nullable=False)
    sunday = Column(Integer, nullable=False)
    start_date = Column(String, nullable=False)
    end_date = Column(String, nullable=False)

class shapes(Base):
    __tablename__ = 'shapes'
    shape_id = Column(String, primary_key=True)
    shape_pt_sequence = Column(Integer, nullable=False)
    shape_pt_lat = Column(Float, nullable=False)
    shape_pt_lon = Column(Float, nullable=False)

class transfers(Base):
    __tablename__ = 'transfers'
    id = Column(Integer, primary_key=True)
    from_stop_id = Column(String, ForeignKey('stops.stop_id'))
    to_stop_id = Column(String, ForeignKey('stops.stop_id'))
    transfer_type = Column(Integer, nullable=False)
    min_transfer_time = Column(Integer, CheckConstraint('min_transfer_time >= 0'))

# 未来可能的实时缓存数据保存在这里(不是最终版)
# # 定义 ORM 模型
# class FeedEntity(Base):
#     __tablename__ = "feed_entity"
#     id = Column(String, primary_key=True)
#     is_deleted = Column(Boolean, default=False, nullable=True)
#     trip_update_id = Column(Integer, ForeignKey("trip_update.id"), nullable=True)
#     vehicle_id = Column(Integer, ForeignKey("vehicle_position.id"), nullable=True)
#     alert_id = Column(Integer, ForeignKey("alert.id"), nullable=True)

#     trip_update = relationship("TripUpdate", back_populates="feed_entity")
#     vehicle = relationship("VehiclePosition", back_populates="feed_entity")
#     alert = relationship("Alert", back_populates="feed_entity")
#     #第一个参数是 Python 类名（不是表名）
#     #第二个参数是 ORM 类中的属性名（不是表名）

# class TripUpdate(Base):
#     __tablename__ = "trip_update"
#     id = Column(Integer, primary_key=True, autoincrement=True)
#     trip_id = Column(String)
#     route_id = Column(String)
#     arrival_time = Column(Integer)
#     departure_time = Column(Integer)

#     feed_entity = relationship("FeedEntity", back_populates="trip_update")

# class VehiclePosition(Base):
#     __tablename__ = "vehicle_position"
#     id = Column(Integer, primary_key=True, autoincrement=True)
#     latitude = Column(Float)
#     longitude = Column(Float)
#     speed = Column(Float)
#     bearing = Column(Float)

#     feed_entity = relationship("FeedEntity", back_populates="vehicle")

# class Alert(Base):
#     __tablename__ = "alert"
#     id = Column(Integer, primary_key=True, autoincrement=True)
#     header_text = Column(String)
#     description_text = Column(String)
#     effect = Column(String)

#     feed_entity = relationship("FeedEntity", back_populates="alert")

# 创建数据库表
Base.metadata.create_all(engine)