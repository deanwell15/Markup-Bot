create database if not exists main;

create table if not exists user_types (
id int primary key not null auto_increment,
user_type varchar(256)
);

insert into user_types (id, user_type)
values (1, 'user'), (2, 'admin');

create table if not exists users (
user_id int primary key auto_increment,
user_name varchar(256),
user_password varchar(256),
user_type int
);

insert into users (user_name, user_password, user_type)
values ('admin', '1234', 2);

create table if not exists images (
id int primary key not null auto_increment,
classifications text,
name text
);

create table if not exists image_availability (
image_id int,
user_id int
);

create table if not exists user_images (
user_id int,
image_id int,
classification text
);