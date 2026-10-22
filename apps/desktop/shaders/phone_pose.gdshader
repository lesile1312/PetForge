shader_type canvas_item;
uniform sampler2D next_texture : source_color;
uniform float pose_mix = 0.0;
uniform float right_press = 0.0;
uniform float left_press = 0.0;
uniform float swipe_amount = 0.0;
uniform vec2 phone_a = vec2(124.6,168.0);
uniform vec2 phone_b = vec2(124.6,168.0);
varying vec2 next_uv;

void vertex() {
    next_uv = COLOR.rg;
}

float skin_weight(vec3 c) {
    // Existing warm skin colors; exclude the purple phone and blue bracelet.
    return smoothstep(.025,.10,c.r-c.b)*smoothstep(.015,.08,c.g-c.b);
}

vec2 finger_delta(vec2 p, vec2 phone) {
    vec2 q = p-phone;
    float right_thumb = 1.0-smoothstep(.35,1.0,length((q-vec2(12.0,1.4))/vec2(7.6,5.0)));
    float left_thumb = 1.0-smoothstep(.35,1.0,length((q-vec2(-7.2,1.7))/vec2(7.0,4.8)));
    vec2 delta = right_thumb*vec2(-2.25*right_press,-1.65*right_press-3.1*swipe_amount);
    delta += left_thumb*vec2(1.7*left_press,-1.25*left_press);
    return delta;
}

void fragment() {
    vec2 size = vec2(256.0,244.0);
    vec2 delta_a = finger_delta(UV*size,phone_a);
    vec2 delta_b = finger_delta(next_uv*size,phone_b);
    // Include both current and displaced skin coverage to move the thumb edge.
    float skin_a = max(skin_weight(texture(TEXTURE,UV).rgb),skin_weight(texture(TEXTURE,UV-delta_a/size).rgb));
    float skin_b = max(skin_weight(texture(next_texture,next_uv).rgb),skin_weight(texture(next_texture,next_uv-delta_b/size).rgb));
    vec4 a = texture(TEXTURE,UV-delta_a*skin_a/size);
    vec4 b = texture(next_texture,next_uv-delta_b*skin_b/size);
    // Mix premultiplied colors in one draw, avoiding translucent overlapping bodies.
    vec4 c = mix(vec4(a.rgb*a.a,a.a),vec4(b.rgb*b.a,b.a),pose_mix);
    COLOR = vec4(c.rgb/max(c.a,.00001),smoothstep(.08,.55,c.a));
}
