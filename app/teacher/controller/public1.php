<?php

namespace app\controller;

//use think\Request;
use think\facade\Request;

class public1
{
    /**
     * @var \think\Request Request实例
     */
    protected $request;
    
    /**
     * 构造方法
     * @param Request $request Request对象
     * @access public
     */
    public function __construct(Request $request)
    {
		$this->request = $request;
    }
    
    public function index()
    {
		dump( $_SERVER);//Request::url();
		dump( $_COOKIE);
		//dump($this->request);
		return "";//$this->request->param('name');
    }    
}