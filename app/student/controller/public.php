<?php
namespace app\controller;

use think\Request;
class public1
{
	public function index(Request $request)
	{
		return $request->param('name');
	}
}