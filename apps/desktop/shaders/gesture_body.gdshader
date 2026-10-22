shader_type canvas_item;

uniform float arm_amount = 0.0;
uniform float head_angle = 0.0;
uniform float head_drop = 0.0;
uniform float blink_amount = 0.0;
uniform float greeting_smile = 0.0;
uniform float mouth_smile = 0.0;
uniform float soft_smile = 0.0;
uniform float gesture_blink = 0.0;
uniform float head_clip_y = 244.0;
uniform float head_clip_feather_px = 0.0;
uniform vec2 gaze_offset_px = vec2(0.0);
uniform sampler2D blink_texture : source_color;
uniform vec2 frame_size = vec2(256.0, 244.0);
uniform vec2 arm_polygon[24];
uniform int arm_polygon_count = 0;

float arm_mask(vec2 p) {
	bool inside = false;
	float nearest = 1000.0;
	for (int i = 0; i < 24; i++) {
		if (i >= arm_polygon_count) { break; }
		int j = i + 1;
		if (j >= arm_polygon_count) { j = 0; }
		vec2 a = arm_polygon[i];
		vec2 b = arm_polygon[j];
		vec2 ab = b - a;
		float h = clamp(dot(p - a, ab) / max(dot(ab, ab), 0.0001), 0.0, 1.0);
		nearest = min(nearest, length(p - a - h * ab));
		if ((a.y > p.y) != (b.y > p.y)) {
			float crossing = (b.x - a.x) * (p.y - a.y) / (b.y - a.y) + a.x;
			if (p.x < crossing) { inside = !inside; }
		}
	}
	return 1.0 - smoothstep(-0.55, 0.55, inside ? -nearest : nearest);
}

float eye_patch_mask(vec2 p, vec2 center) {
	// Include the complete original iris and outer lash; a small circular patch
	// left part of the right eye behind when the lids were fully closed.
	vec2 q = (p - center) / vec2(14.0, 10.5);
	return 1.0 - smoothstep(0.88, 1.08, length(q));
}

void fragment() {
	vec2 p = UV * frame_size;
	vec2 source = p;
	if (abs(head_angle) + abs(head_drop) > 0.00001) {
		float weight = 1.0 - smoothstep(103.0, 127.0, p.y);
		float angle = -head_angle * weight;
		vec2 offset = p - vec2(128.0, 112.0) - vec2(0.0, head_drop * weight);
		float c = cos(angle);
		float s = sin(angle);
		source = vec2(c * offset.x - s * offset.y, s * offset.x + c * offset.y) + vec2(128.0, 112.0);
	}
	// Shape the existing mouth gently, preserving a single coherent mouth drawing.
	vec2 mouth_local = source - vec2(128.0,94.0);
	float mouth_weight = 1.0-smoothstep(.65,1.0,length(mouth_local/vec2(10.0,5.0)));
	source.x -= mouth_local.x*.08*soft_smile*mouth_weight;
	source.y += (.6*pow(clamp(abs(mouth_local.x)/7.0,0.0,1.0),2.0)-.12)*soft_smile*mouth_weight;
	vec2 face_source = source;
	// Shift only the open iris. Closed lids retain their own undistorted coordinates.
	float left_iris = 1.0 - smoothstep(0.50, 1.0, length((source - vec2(107.0, 75.0)) / vec2(6.5, 8.5)));
	float right_iris = 1.0 - smoothstep(0.50, 1.0, length((source - vec2(150.0, 75.0)) / vec2(6.5, 8.5)));
	source -= gaze_offset_px * max(left_iris, right_iris);
	vec4 color = texture(TEXTURE, source / frame_size);
	float closure = clamp(max(max(blink_amount, gesture_blink), greeting_smile), 0.0, 1.0);
	if (closure > 0.0001) {
		bool right_eye = face_source.x > 128.0;
		vec2 center = right_eye ? vec2(149.0, 77.0) : vec2(108.0, 77.0);
		float eye_area = eye_patch_mask(face_source, center);
		// The source illustration's right closed lid sits four pixels lower.
		// Register each lid to the resting face rather than tilting the right eye.
		vec2 closed_source = face_source + (right_eye ? vec2(0.0, 4.0) : vec2(0.0));
		vec4 closed_eye = texture(blink_texture, closed_source / frame_size);
		float upper = mix(66.5, 78.0, closure);
		float lower = mix(86.0, 78.0, closure);
		float gap = max(lower - upper, 0.4);
		vec2 open_source = face_source;
		open_source.y = 66.5 + (face_source.y - upper) * 19.5 / gap;
		float iris = 1.0 - smoothstep(0.5, 1.0, length((open_source - center) / vec2(6.5, 8.5)));
		open_source -= gaze_offset_px * iris;
		vec4 open_eye = texture(TEXTURE, open_source / frame_size);
		float aperture = smoothstep(upper - 0.45, upper + 0.45, face_source.y)
			* (1.0 - smoothstep(lower - 0.45, lower + 0.45, face_source.y));
		aperture *= 1.0 - smoothstep(0.82, 0.98, closure);
		vec4 lid_color = mix(closed_eye, open_eye, aperture);
		color = mix(color, lid_color, eye_area * smoothstep(0.0, 0.12, closure));
	}
	if (max(greeting_smile, mouth_smile) > 0.0001) {
		vec4 closed_face = texture(blink_texture, face_source / frame_size);
		float mouth_area = 1.0 - smoothstep(0.70, 1.0, length((face_source - vec2(128.0, 94.0)) / vec2(11.0, 6.0)));
		color = mix(color, closed_face, mouth_area * max(greeting_smile, mouth_smile));
	}
	if (arm_amount > 0.0001 && arm_polygon_count > 2) {
		color.a *= 1.0 - arm_amount * arm_mask(p);
	}
	if (head_clip_feather_px > 0.0) {
		color.a *= 1.0 - smoothstep(head_clip_y - head_clip_feather_px, head_clip_y, source.y);
	} else if (source.y >= head_clip_y) {
		color.a = 0.0;
	}
	COLOR = color;
}
